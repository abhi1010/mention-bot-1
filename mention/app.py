#!/usr/bin/env python
# coding: utf-8
import json
import logging

from flask import Flask, request


## setup logging

import logging.config

logger = logging.getLogger(__name__)

logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'basic': {
            'format': '%(levelname)s %(asctime)s %(filename)s:%(lineno)d '
            '%(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'basic'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'basic',
            'filename': 'log-mention.log',
            'maxBytes': '10240',
            'backupCount': '3',
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file']
    }
})


## end logging setup
from mention import gitlab_client
from mention import mention_bot
from mention import config
from mention import helper

app = Flask(__name__)


@app.route('/check_health', methods=['GET'])
def check_health():
    return "mention-bot"


@app.route('/', methods=['GET'])
def mentionbot():
    return "Gitlab Mention Bot active"


@app.route('/', methods=['POST'])
def webhook():
    event = request.headers.get('X-Gitlab-Event')
    if not event:
        return '', 400
    if event != 'Merge Request Hook':
        return '', 200
    payload = json.loads(request.data)
    logger.info('_' * 80)
    logger.info('received webhook: {}'.format(helper.load_dict_as_yaml(payload)))

    username = payload['user']['username']
    project_id = payload['object_attributes']['target_project_id']
    target_branch = payload['object_attributes']['target_branch']
    namespace = payload['object_attributes']['target']['path_with_namespace']
    merge_request_id = payload['object_attributes']['iid']
    # loading config
    logger.info(
        'Current Action={}'.format(payload['object_attributes']['action']))
    try:
        cfg = mention_bot.get_repo_config(project_id, target_branch,
                                          config.CONFIG_PATH)
        diff_files = []

        if mention_bot.is_valid(cfg, payload):
            diff_files = mention_bot.get_diff_files(project_id,
                                                    merge_request_id)
            owners = mention_bot.guess_owners_for_merge_reqeust(
                project_id, namespace, target_branch, merge_request_id,
                username, cfg, diff_files)
            mention_bot.add_comment(project_id, merge_request_id, username,
                                    owners, cfg)

        if payload['object_attributes']['action'] in [
                'open', 'reopen', 'closed', 'close', 'merge'
        ]:
            mention_bot.manage_labels(payload, project_id, merge_request_id,
                                      cfg, diff_files)
    except gitlab_client.ConfigSyntaxError as e:
        gitlab_client.add_comment_merge_request(project_id, merge_request_id,
                                                e.message)
    return "", 200


def main():
    config.check_config()
    app.run(host='0.0.0.0')


if __name__ == '__main__':
    main()
