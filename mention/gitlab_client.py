#!/usr/bin/env python
# coding: utf-8
from __future__ import absolute_import
import re
import logging
import pprint
import base64
from itertools import chain

import sys, os

import requests
from gitlab import Gitlab

from mention.config import GITLAB_URL, GITLAB_TOKEN
from mention.config import GITLAB_USERNAME, GITLAB_PASSWORD

logger = logging.getLogger(__name__)

session = None
_gitlab_client = None


class GitlabError(Exception):
    pass


class ConfigSyntaxError(Exception):
    pass


def get_pretty_print(item, depth=None):
    pp = pprint.PrettyPrinter(indent=4, depth=depth)
    return pp.pformat(item)


PP = lambda x: get_pretty_print(x)


def get_channels_based_on_labels(cfg, labels):
    labels = labels or ['']
    channels = list(
        set([y for x, y in cfg.labelNotifications.items() if x in labels]))
    return channels


def get_payload_labels(payload):
    return [l[u'title'].encode('utf-8')
            for l in payload[u'labels']] if u'labels' in payload else []


def get_labels(cfg, files):
    labels_to_add = []
    files_to_use = [x[0] for x in files]
    for file in files_to_use:
        for path, label in cfg.labels.items():
            if file.startswith(path):
                labels_to_add.append(label)
    return sorted([x.encode('utf-8') for x in list(set(labels_to_add))])


def get_gitlab_client():
    global session
    setup_cookie()
    global _gitlab_client
    if _gitlab_client is None:
        logger.info('creating session first time')
        _gitlab_client = Gitlab(GITLAB_URL,
                                api_version='4',
                                private_token=GITLAB_TOKEN,
                                session=session)
    return _gitlab_client

def get_project(project_id):
    client = get_gitlab_client()
    project = client.projects.get(project_id)
    return project

def get_merge_request(project_id, merge_request_id):
    project = get_project(project_id)
    mr = project.mergerequests.get(merge_request_id)
    return mr

def add_comment_merge_request(project_id, merge_request_id, note):
    merge_request = get_merge_request(project_id, merge_request_id)
    res = merge_request.notes.create({u'body': note})
    return res.attributes

def get_active_users():
    client = get_gitlab_client()
    return [u.attributes[u'username'].encode('utf-8')
            for u in client.users.list(all=True)
            if u.attributes[u'state'] == u'active']

def get_blocked_users():
    client = get_gitlab_client()
    # for u in client.users.list(all=True):
    #     logger.info('custom users = {}'.format(u.attributes[u'username']))
    blocked_users = [
        u.attributes[u'username'].encode('utf-8')
            for u in client.users.list(all=True)
        if u.attributes[u'state'] != u'active'
    ]

    return blocked_users


def update_labels(project_id, merge_request_id, labels_list):
    merge_request = get_merge_request(project_id, merge_request_id)
    merge_request.labels = labels_list
    merge_request.save()
    # client = get_gitlab_client()
    # res = client.updatemergerequest(
    #     project_id, merge_request_id, labels=labels)
    # logger.info('merge_request= {}; dir={}'.format(res, dir(res)))
    # return 'kk'


def get_merge_request_plain_changes(project_id, merge_request_id):
    mr = get_merge_request(project_id, merge_request_id)
    commits = mr.commits()
    changes = ''
    for d in commits:
        # logger.info('commit = {}'.format(d.diff()))
        ch = '\n'.join([x[u'diff'] for x in d.diff()])
        changes += ch
    return changes

def get_merge_request_diff(project_id, merge_request_id):
    mr = get_merge_request(project_id, merge_request_id)
    diffs = mr.diffs.list(all=True)
    uniq_diffs = set()
    changes = []
    for d in diffs:
        diff = mr.diffs.get(d.attributes[u'id'])
        if diff.attributes[u'base_commit_sha'] not in uniq_diffs:
            uniq_diffs.add(diff.attributes[u'base_commit_sha'])
            logger.info('adding for ' + diff.attributes[u'base_commit_sha'])
            changes.append(diff.attributes[u'diffs'])
        # logger.info('diff = {}'.format(diff.attributes[u'diffs'][u'diff']))
    changes = list(chain(*changes))
    logger.info('changes = {}'.format(changes))
    return changes


# def get_merge_request_diff(project_id, merge_request_id):
#     client = get_gitlab_client()
#     changes = client.getmergerequestchanges(project_id, merge_request_id)
#     return changes['changes']


def has_mention_comment(project_id, merge_request_id, comment):
    merge_request = get_merge_request(project_id, merge_request_id)
    notes = merge_request.notes.list(all=True)
    discussions = [n.attributes[u'body'].encode('utf-8') for n in notes]
    return comment in discussions


def get_project_file(project_id, branch, path):
    project = get_project(project_id)
    f = project.files.get(file_path=path, ref=branch)
    content = base64.b64decode(f.attributes[u'content'])
    return content


def _search_authenticity_token(html):
    matched = re.search(
        r'<input type="hidden" name="authenticity_token" value="(.*)" />',
        html)
    if not matched:
        raise GitlabError("Fetch login page failed.")
    return matched.group(1)

def login():
    global session
    SIGN_IN_URL = GITLAB_URL + '/users/sign_in'
    LOGIN_URL = GITLAB_URL + '/users/sign_in'
    if session:
        logger.info('session exists')
    else:
        logger.info('no session')
    session = requests.Session()

    sign_in_page = session.get(SIGN_IN_URL).content
    for l in sign_in_page.split('\n'):
        m = re.search('name="authenticity_token" value="([^"]+)"', l)
        if m:
            break

    token = None
    if m:
        token = m.group(1)

    if not token:
        logger.info('Unable to find the authenticity token')
        sys.exit(1)
    data = {'user[login]': GITLAB_USERNAME,
            'user[password]': GITLAB_PASSWORD,
            'authenticity_token': token}
    r = session.post(LOGIN_URL, data=data)
    if r.status_code != 200:
        logger.info('Failed to log in with status: {}. content={}'.format(
            r.status_code, r.content
        ))
    else:
        logger.info('LOGIN WORKED')

    session.headers.update({'Private-Token': GITLAB_TOKEN})


def setup_cookie():
    global session
    if not session:
        logger.info('cookies need a setup')
        login()
    else:
        logger.info('cookies not needed')


def fetch_blame(namespace, target_branch, path):
    setup_cookie()
    try:
        url = '%s/%s/blame/%s/%s' % (GITLAB_URL, namespace, target_branch,
                                     path)
        logger.info('fetch_blame: locals={}'.format(locals()))
        response = session.get(url)
        logger.info('response status={}; content={}'.format(
            response.status_code, response.content
        ))
        response.raise_for_status()
    except requests.HTTPError:
        logger.warning("Fetch blame failed: {}".format(url))
    return ''
