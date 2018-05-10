import sys
import json
import logging

from slacker import Slacker

from mention.config import SLACK_TOKEN

logger = logging.getLogger(__name__)


def send_to_slack(text, msg, channels):
    slack = Slacker(SLACK_TOKEN)
    for channel in channels:
        slack.chat.post_message(
            channel, text=text, attachments=msg, as_user=False)


_LABELS_FORMAT = '''{{
                    "title": "Labels",
                    "value": "{LABELS}",
                    "short": true
                }},'''
_FORMAT = '''
[
    {{
        "fallback": "{TITLE}",
        "color": "{COLOR}",
        "mrkdwn_in": ["text", "pretext", "fields"],
        "author_name": "{AUTHOR}",
        "author_link": "{AUTHOR_LINK}",
        "author_icon": "http://cdn0.iconfinder.com/data/icons/development-2/24/pull-request-256.png",
        "title": "{TITLE}",
        "title_link": "{TITLE_LINK}",
        "fields": [
            {{
                "title": "Repo",
                "value": "<http://gitlab/p/higgs/|higgs>",
                "short": true
            }},
            {LABELS}
            {{
                "title": "Status",
                "value": "{STATUS}",
                "short": true
            }}
        ],
        "footer": "Gitlab Message Bot",
        "footer_icon": "https://png.icons8.com/color/1600/gitlab.png"
    }}
]

'''


def create_slack_msg_long(data, labels):
    '''
    Helps you create a slack message in the long format.
    It contains details as attachments instead of being in one line.
    Color coded 
    :param data:
    :param labels:
    :return:
    '''

    def _get_color(action):
        color = '#40c057'  # 'open'
        if action in ['update', 'reopen']:
            color = 'fab005'
        elif action in ['close', 'closed']:
            color = '#e03131'
        elif action in ['merged', 'merge']:
            color = '#4c6ef5'
        return color

    def _create_slack_msg_long(title, color, author, author_link, title_link,
                               text, labels, status):
        return _FORMAT.format(
            TITLE=title,
            COLOR=color,
            AUTHOR=author,
            AUTHOR_LINK=author_link,
            TITLE_LINK=title_link,
            TEXT='*Desc*: {}'.format(text),
            LABELS=labels,
            STATUS=status)

    obj = data['object_attributes']
    action = obj['action']
    title = '{}: {}'.format(obj['iid'], obj['title'])
    color = _get_color(action)
    author = data['user']['username']
    author_link = data['user']['avatar_url']
    title_link = obj['url']
    text = obj['description']
    status = action
    labels_str = _LABELS_FORMAT.format(LABELS=labels) if labels else ''
    return text, _create_slack_msg_long(title, color, author, author_link,
                                        title_link, text, labels_str, status)


_FMTS_SHORT = '{AUTHOR} {STATUS} *!{IID}* in _<http://gitlab/p/higgs/|p/higgs>_: *<{TITLE_LINK}|{TITLE}>* {LABELS}'
_STATUS_REPLACEMENTS = {
    'open': 'opened',
    'close': 'closed',
    'merge': 'merged',
    'reopen': 'reopened'
}


def create_slack_msg_short(data, labels):
    obj = data['object_attributes']
    return _FMTS_SHORT.format(
        AUTHOR=data['user']['username'],
        STATUS=_STATUS_REPLACEMENTS[obj['action']]
        if obj['action'] in _STATUS_REPLACEMENTS else obj['action'],
        IID=obj['iid'],
        TITLE_LINK=obj['url'],
        TITLE=obj['title'],
        LABELS='_({})_'.format(labels) if labels else ''), None
