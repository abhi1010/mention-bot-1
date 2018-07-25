#!/usr/bin/env python
# coding: utf-8
from __future__ import absolute_import
import re
import logging
import pprint
import base64

import requests
from gitlab import Gitlab

from mention.config import GITLAB_URL, GITLAB_TOKEN
from mention.config import GITLAB_USERNAME, GITLAB_PASSWORD

logger = logging.getLogger(__name__)

session = requests.Session()
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
    global _gitlab_client
    if _gitlab_client is None:
        _gitlan_client = Gitlab(GITLAB_URL, private_token=GITLAB_TOKEN)
    return _gitlan_client

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
            for u in client.users.list(active=True)]

def get_blocked_users():
    client = get_gitlab_client()
    for u in client.users.list(all=True):
        print('custom users = {}'.format(u.attributes[u'username']))
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
    # print('merge_request= {}; dir={}'.format(res, dir(res)))
    # return 'kk'


def get_merge_request_diff(project_id, merge_request_id):
    mr = get_merge_request(project_id, merge_request_id)
    commits = mr.commits()
    changes = ''
    for d in commits:
        # print('commit = {}'.format(d.diff()))
        ch = '\n'.join([x[u'diff'] for x in d.diff()])
        changes += ch
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


# def get_project_file(project_id, branch, path):
#     client = get_gitlab_client()
#     return client.getrawfile(project_id, branch, path)



def _search_authenticity_token(html):
    matched = re.search(
        r'<input type="hidden" name="authenticity_token" value="(.*)" />',
        html)
    if not matched:
        raise GitlabError("Fetch login page failed.")
    return matched.group(1)


def login():
    login_url = GITLAB_URL + '/users/auth/ldapmain/callback'
    login_page = GITLAB_URL + '/users/sign_in'
    headers = {
        'Origin': GITLAB_URL,
        'Referer': login_page,
    }
    response = session.get(login_url, headers=headers)
    authenticity_token = _search_authenticity_token(response.text)
    data = {
        'username': GITLAB_USERNAME,
        'password': GITLAB_PASSWORD,
        'authenticity_token': authenticity_token,
        'utf8': u'√',
    }
    return session.post(
        login_url, headers=headers, data=data, allow_redirects=False)


def setup_cookie():
    if session.cookies is None or len(session.cookies) == 0:
        login()


def fetch_blame(namespace, target_branch, path):
    setup_cookie()
    try:
        url = '%s/%s/blame/%s/%s' % (GITLAB_URL, namespace, target_branch,
                                     path)
        logger.info('fetch_blame: locals={}'.format(PP(locals())))
        response = session.get(url)
        response.raise_for_status()
    except requests.HTTPError:
        logger.warning("Fetch %s blame failed.".format(url))
    return response.text
