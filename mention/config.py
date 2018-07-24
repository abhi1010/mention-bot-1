#!/usr/bin/env python
# coding: utf-8
import os
import json
import logging

GITLAB_URL = os.getenv('GITLAB_URL') or 'http://example.com'
GITLAB_TOKEN = os.getenv('GITLAB_TOKEN')
GITLAB_USERNAME = os.getenv('GITLAB_USERNAME')
GITLAB_PASSWORD = os.getenv('GITLAB_PASSWORD')
SLACK_TOKEN = os.getenv('SLACK_TOKEN')
CONFIG_PATH = '.mention-bot'


logger = logging.getLogger(__name__)


def get_default_config():
    file_path = 'sample-mention-bot.json'
    with open(file_path, 'rt') as file_placeholder:
        lines = file_placeholder.readlines()
        text = ''.join(lines)
        config_as_dict = json.loads(text)
        return config_as_dict


def check_config():
    if not GITLAB_URL:
        logger.error(
            "No Gitlab address detected, please expose GITLAB_URL as environment variables."
        )
        exit(1)

    if not GITLAB_TOKEN:
        logger.error(
            "goto Profile Settings -> Access Token -> Create Personal Access Token"
        )
        logger.error("append GITLAB_TOKEN= before start command.")
    else:
        logger.info('GITLAB_TOKEN = {}'.format(GITLAB_TOKEN))
    if not SLACK_TOKEN:
        logger.error("Create a valid slack token first.")
        logger.error("append SLACK_TOKEN= before start command.")
        exit(1)
