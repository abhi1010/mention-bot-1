#!/usr/bin/env python
# coding: utf-8
import re
import json
import logging
from collections import defaultdict
from fnmatch import fnmatch

from mention import notify
from mention import config
from mention import gitlab_client

logger = logging.getLogger(__name__)

RE_DIFF_LINE_NO = re.compile(r'\@\@ -(\d+),?(\d+)? \+(\d+),?(\d+)? \@\@')
RE_BLAME_OR_NO = re.compile(
    r'(<a class=.commit-author-link. *href="\/([\w\-0-9.]+)|<a class=.diff-line-num.)'
)


class BotConfig(object):
    default_config = config.get_default_config()

    @classmethod
    def from_dict(cls, d):
        cfg = cls()
        attrs = dict(cls.default_config, **d)
        for k, v in attrs.items():
            setattr(cfg, k, v)
        return cfg


def parse_diff_file(lines):
    deleted_lines = []
    current_from_line = 0
    lines = list(lines)
    while len(lines) > 0:
        line = lines.pop()
        if line.startswith('---') or line.startswith('+++'):
            continue
        if line.startswith('@@'):
            matched = RE_DIFF_LINE_NO.match(line)
            if matched is None:
                continue
            from_line = matched.group(1)
            # from_count = matched.group(2)
            # to_line = matched.group(3)
            # to_count = matched.group(4)
            current_from_line = int(from_line)
            continue
        if line.startswith('-'):
            deleted_lines.append(current_from_line)
        if not line.startswith('+'):
            current_from_line += 1
    return deleted_lines


def parse_diff(changes):
    files = []
    for diff in changes:
        from_file = diff['old_path']
        lines = diff['diff'].split('\n')
        deleted_lines = parse_diff_file(reversed(lines))
        files.append((from_file, deleted_lines))
    return files


def parse_blame(blame):
    lines = []
    current_author = 'none'
    result = RE_BLAME_OR_NO.finditer(blame) if blame else ''

    for matches in result:
        if matches.group(2):
            current_author = matches.group(2)
        else:
            lines.append(current_author)
    return lines


def get_deleted_owners(files, blames):
    owners = defaultdict(int)
    for file_path, deleted_lines in files:
        blame = blames.get(file_path)
        if not blame:
            continue
        for line in deleted_lines:
            author_name = blame[line - 1]
            if not author_name:
                continue
            owners[author_name] += 1
    return owners


def get_all_owners(files, blames):
    owners = defaultdict(int)
    for file_path, deleted_lines in files:
        blame = blames.get(file_path, None)
        if blame is None:
            continue
        for author_name in blame:
            owners[author_name] += 1
    return owners


def sort_owners(owners):
    owner_names = owners.keys()
    return sorted(owner_names, key=lambda k: owners[k], reverse=True)


def guess_owners(files, blames, creator, cfg):
    if files:
        deleted_owners = get_deleted_owners(files, blames)
        all_owners = get_all_owners(files, blames)

        deleted_owners = sort_owners(deleted_owners)
        all_owners = sort_owners(all_owners)

        deleted_owners_set = set(deleted_owners)
        other_owners = [
            owner for owner in all_owners if owner not in deleted_owners_set
        ]

        owners = deleted_owners + other_owners
        active_users = gitlab_client.get_active_users()

        def filter_owners(owner):
            return all([
                owner != creator, owner != 'none',
                owner not in cfg.userBlacklist, owner in active_users
            ])

        logger.info('guess_owners: locals={}'.format(locals()))
        return [u for u in owners if filter_owners(u)][:cfg.maxReviewers]
    return []


def filter_files(files, fileBlacklist, numFilesToCheck):
    def filter_file_black_list(files):
        new_files = []
        for filename, lines in files:
            flag = False
            for pattern in fileBlacklist:
                if fnmatch(filename, pattern):
                    flag = True
            if not flag:
                new_files.append((filename, lines))
        return new_files

    files = sorted(files, key=lambda f: len(f[1]), reverse=True)
    if len(fileBlacklist) > 0:
        files = filter_file_black_list(files)
    return files[:numFilesToCheck]


def get_files_blames(repo_namespace, target_branch, files):
    blames = {}
    for from_file, linenos in files:
        blame = gitlab_client.fetch_blame(repo_namespace, target_branch,
                                          from_file)
        logger.info('file={}; lines={}'.format(from_file, linenos))
        logger.info('blame.len={}; blame = {}'.format(
            len(blame),
            blame.encode('ascii', 'ignore').decode('ascii')))
        parsed_blame = parse_blame(blame)
        blames[from_file] = parsed_blame
        logger.info('file: {}; parsed_blame={}'.format(from_file,
                                                       parsed_blame))
    return blames


def _set_labels(labels, diff_files, project_id, merge_request_id):
    logger.info('labels={}; diff_files={}'.format(
        labels, gitlab_client.PP(diff_files)))
    labels_in_str = ','.join(labels)
    if labels_in_str:
        gitlab_client.update_labels(project_id, merge_request_id, labels)
    logger.info('labels updated on gitlab MR')


def _manage_labels(project_id, merge_request_id, cfg, diff_files, labels,
                   username, action, iid, url, title):
    _set_labels(labels, diff_files, project_id, merge_request_id)

    channels = gitlab_client.get_channels_based_on_labels(cfg, labels)
    logger.info('channels={}'.format(channels))

    text, msg = notify.get_slack_msg_short(labels, username, action, iid, url,
                                           title)

    logger.info('slack msg={}'.format(msg))
    notify.send_to_slack(text, msg, channels)
    logger.info('msg sent to slack on channels: {}'.format(channels))


def get_diff_files(project_id, merge_request_id):
    changes = gitlab_client.get_merge_request_diff(project_id,
                                                   merge_request_id)
    files = parse_diff(changes)
    if not files:
        logger.info('No files found. Changes were: {}'.format(changes))
    return files


def manage_labels(payload, project_id, merge_request_id, cfg, diff_files):
    labels = gitlab_client.get_labels(
        cfg, diff_files) or gitlab_client.get_payload_labels(payload)
    username = payload['user']['username']

    obj = payload['object_attributes']
    action = obj['action']
    iid = obj['iid']
    url = obj['url']
    title = obj['title']

    _manage_labels(project_id, merge_request_id, cfg, diff_files, labels,
                   username, action, iid, url, title)


# IMP function
def guess_owners_for_merge_reqeust(project_id, namespace, target_branch,
                                   merge_request_id, creator, cfg, diff_files):
    if not cfg.findPotentialReviewers:
        return []
    files = filter_files(diff_files, cfg.fileBlacklist, cfg.numFilesToCheck)
    blames = get_files_blames(namespace, target_branch, files)
    return guess_owners(files, blames, creator, cfg)


def add_comment(project_id, merge_request_id, creator, reviewers, cfg):
    if not cfg.createComment:
        return
    msg = """{0}, thanks for your MR!
    By analyzing the history of the files in this pull request,
    we identified {1} to be potential reviewers."""
    reviewers_mentions = map(lambda r: '@' + str(r), reviewers)
    if not reviewers_mentions:
        logger.info('No valid reviewers. Ignoring')
        return False
    note = msg.format(creator, ' and '.join(reviewers_mentions))
    if cfg.skipAlreadyMentionedMR and\
       gitlab_client.has_mention_comment(project_id, merge_request_id, note):
        return False
    return gitlab_client.add_comment_merge_request(project_id,
                                                   merge_request_id, note)


def get_repo_config(project_id, target_branch, config_path):
    filecontent = gitlab_client.get_project_file(project_id, target_branch,
                                                 config_path)
    if not filecontent:
        logger.warning(
            "Unable to find config file, use default config instead.")
        return BotConfig.from_dict(config.get_default_config())
    try:
        cfg = json.loads(filecontent)
        return BotConfig.from_dict(cfg)
    except Exception:
        logger.exception("Failed to parse config: %s" % filecontent)
        raise gitlab_client.ConfigSyntaxError(
            "Unable to parse mention-bot custom configuration file due to a syntax error."
        )


# we expected payload here
def is_valid(cfg, data):
    if data['object_attributes']['action'] not in cfg.actions:
        return False

    if cfg.skipWIP and data['object_attributes']['work_in_progress']:
        return False

    if cfg.skipAlreadyAssignedMR and 'assignee' not in data[
            'object_attributes']:
        return False
    return True


def check_merge_requests(repo_name):
    project = gitlab_client.get_project(repo_name)
    project_id = project.attributes['id']
    target_branch = 'master'

    cfg = get_repo_config(project_id, target_branch, config.CONFIG_PATH)
    all_mrs = project.mergerequests.list(state='opened', all=True)

    unlabelled_mrs = list(
        filter(lambda mr: not mr.attributes['labels'], all_mrs))

    for mr in unlabelled_mrs:
        logging.info(f'\n\nMR: {mr}')
        mr_attrs = mr.attributes
        merge_request_id = mr_attrs['iid']
        diff_files = get_diff_files(project_id, merge_request_id)
        labels = gitlab_client.get_labels(cfg, diff_files)
        print(f' labels={labels}')
        if labels:
            # print(f'ABHI            Mr: {mr_attrs["id"]} ; labels={labels}')
            _set_labels(labels, diff_files, project_id, merge_request_id)
        else:
            print(f'No Labels for MR: {mr_attrs}')

    logging.info(f'total = {len(unlabelled_mrs)}')
