#!/usr/bin/env python
# coding: utf-8
from __future__ import absolute_import

import mock
import flask_testing

from mention.app import app
from mention.mention_bot import BotConfig
from mention.config import get_default_config


class TestBot(flask_testing.TestCase):
    def create_app(self):
        app.config['TESTING'] = True
        return app

    @mock.patch('mention.mention_bot.get_repo_config')
    @mock.patch('mention.mention_bot.is_valid')
    @mock.patch('mention.mention_bot.add_comment')
    @mock.patch('mention.mention_bot.guess_owners_for_merge_reqeust')
    def test_webhook_invalid(self, guess_owners_for_merge_reqeust, add_comment,
                             is_valid, get_repo_config):
        guess_owners_for_merge_reqeust.return_value = ['lfyzjck']
        is_valid.return_value = False
        headers = {'X-Gitlab-Event': 'Merge Request Hook'}
        with open('tests/data/merge_request_event.json') as f:
            data = f.read()
            response = self.client.post('/', data=data, headers=headers)
            self.assertEqual(response.status_code, 200)

    @mock.patch('mention.mention_bot.get_repo_config')
    @mock.patch('mention.mention_bot.is_valid')
    @mock.patch('mention.mention_bot.add_comment')
    @mock.patch('mention.mention_bot.get_diff_files')
    @mock.patch('mention.mention_bot.manage_labels')
    @mock.patch('mention.mention_bot.guess_owners_for_merge_reqeust')
    def test_webhook_valid(self, guess_owners_for_merge_reqeust, add_comment,
                           get_diff_files, manage_labels, is_valid,
                           get_repo_config):
        guess_owners_for_merge_reqeust.return_value = ['lfyzjck']
        get_diff_files.return_value = []
        manage_labels.return_value = True
        get_repo_config.return_value = BotConfig.from_dict(
            get_default_config())
        is_valid.return_value = True
        headers = {'X-Gitlab-Event': 'Merge Request Hook'}
        with open('tests/data/merge_request_event.json') as f:
            data = f.read()
            response = self.client.post('/', data=data, headers=headers)
            self.assertEqual(response.status_code, 200)
        add_comment.assert_called()
