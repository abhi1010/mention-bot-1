#!/usr/bin/env python
# coding: utf-8
import json
import logging
from queue import Queue, Empty
from threading import Thread
import datetime
import math
import time
import argparse
import copy

from flask import Flask, request

## setup logging

import logging.config

_DICT_LOG_HOOK = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'basic': {
            'format':
            '%(levelname)s %(asctime)s %(filename)s:%(lineno)d '
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
            'filename': '/tmp/mention-bot-hook.log',
            'maxBytes': 10240,
            'backupCount': 3
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file']
    }
}

_DICT_LOG_CHECKS = copy(_DICT_LOG_HOOK)
_DICT_LOG_CHECKS['handlers']['file'][
    'filename'] = '/tmp/mention-bot-checks.log'

logger = logging.getLogger(__name__)

## end logging setup
from mention import gitlab_client
from mention import mention_bot
from mention import config
from mention import helper

app = Flask(__name__)
_STOP_PROCESS = False
enclosure_queue = Queue()


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

    # add payload to queue so that _payload_worker(q) can process it in
    # a separate thread
    payload = json.loads(request.data)
    enclosure_queue.put((datetime.datetime.now(), payload))

    return "", 200


def _manage_payload(payload):
    logger.info('_' * 80)
    logger.info('Received payload<{}>: {}'.format(
        id(payload), helper.load_dict_as_yaml(payload)))
    username = payload['user']['username']
    project_id = payload['object_attributes']['target_project_id']
    target_branch = payload['object_attributes']['target_branch']
    namespace = payload['object_attributes']['target']['path_with_namespace']
    merge_request_id = payload['object_attributes']['iid']
    # loading config
    logger.info('Current Action={}'.format(
        payload['object_attributes']['action']))
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


def _check_and_sleep(ts):
    now = datetime.datetime.now()
    exp_ts = datetime.timedelta(seconds=10) + ts
    if exp_ts > now:
        should_wait = math.ceil((exp_ts - now).total_seconds())
        if should_wait:
            logger.info('ts={}; now={}; sleeping for: {}'.format(
                ts, now, should_wait))
            time.sleep(should_wait)


def _payload_worker(q):
    # this worker is needed solely because sometimes the MR comes in too fast,
    # and gitlab queries fail. So let's add a delay of 10s, to ensure that
    # all updates work.
    logger.info('Looking for next payload')
    global _STOP_PROCESS
    while not _STOP_PROCESS:
        try:
            payload_ts, payload = q.get(timeout=2)
            logger.info('Looking for next payload')
            logger.info('Payload found: at ts={}; id={}'.format(
                payload_ts, id(payload)))
            _check_and_sleep(payload_ts)
            _manage_payload(payload)
            q.task_done()
        except Empty:
            pass


def main():
    config.check_config()
    # setup thread to handle the payloads
    worker = Thread(target=_payload_worker, args=(enclosure_queue, ))
    worker.setDaemon(True)
    worker.start()

    app.run(host='0.0.0.0')
    global _STOP_PROCESS
    _STOP_PROCESS = True
    logger.info('Stopping worker...')
    worker.join()
    logger.info('worker stopped...')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='Startup Mode')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-listen', action='store_true', default=False)
    group.add_argument('-quick-check', action='store_true', default=False)

    args = parser.parse_args()
    if args.listen:
        logging.config.dictConfig(_DICT_LOG_HOOK)
        main()
    if args.quick_check:
        logging.config.dictConfig(_DICT_LOG_CHECKS)
        mention_bot.check_merge_requests('p/higgs')
