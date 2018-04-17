#!/usr/bin/env python
# coding: utf-8
import json
import logging

from flask import Flask, request

from mention import utils
from mention import mention_bot
from mention import config

app = Flask(__name__)
logger = logging.getLogger(__name__)


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
    logger.info('received webhook: %s' % request.data)
    username = payload['user']['username']
    project_id = payload['object_attributes']['target_project_id']
    target_branch = payload['object_attributes']['target_branch']
    namespace = payload['object_attributes']['target']['path_with_namespace']
    merge_request_id = payload['object_attributes']['id']
    # loading config
    try:
        cfg = mention_bot.get_repo_config(project_id, target_branch,
                                          config.CONFIG_PATH)
        if not mention_bot.is_valid(cfg, payload):
            # skip
            return "", 200
        owners = mention_bot.guess_owners_for_merge_reqeust(
            payload, project_id, namespace, target_branch, merge_request_id,
            username, cfg)
        mention_bot.add_comment(project_id, merge_request_id, username, owners,
                                cfg)
    except utils.ConfigSyntaxError as e:
        utils.add_comment_merge_request(project_id, merge_request_id,
                                        e.message)
    return "", 200


def main():
    config.check_config()
    app.run(host='0.0.0.0')


if __name__ == '__main__':
    main()
