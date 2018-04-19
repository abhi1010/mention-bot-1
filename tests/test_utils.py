import pytest

import unittest
import mock
import json

from mention import utils
from mention import app
from mention import config
from mention import mention_bot
from mention import notify


class TestNotify(unittest.TestCase):
    def test_create_slack_msg(self):
        default_config = mention_bot.BotConfig.from_dict(
            config.get_default_config())
        with open('tests/data/merge_request_event.json') as f:
            data = json.loads(f.read())
            labels = 'ccgh'
            msg = notify.create_slack_msg(data, labels)
            self.assertTrue(len(msg) > 0)


class TestUtils(unittest.TestCase):
    def test_default_config(self):
        assert True

    def test_labels(self):
        files = [
            ('pyapp/riskweb/a.py', [1, 2]),
            ('pyapp/riskweb/a.py', [1, 2]),
            ('pylib/b.py', [1, 2, 3, 5, 6]),
            ('c.json', [1, 2, 3]),
            ('readme.md', [2]),
            ('xx.py', [234, 456, 789]),
        ]
        default_config = mention_bot.BotConfig.from_dict(
            config.get_default_config())
        labels = utils.get_labels(default_config, files)
        self.assertListEqual(labels, sorted(['risk', 'pylib']))

    def test_get_channels_based_on_labels(self):
        default_config = mention_bot.BotConfig.from_dict(
            config.get_default_config())
        channels = utils.get_channels_based_on_labels(default_config,
                                                      ['ccgh', 'risk'])
        self.assertListEqual(channels, ['#slak'])

        channels = utils.get_channels_based_on_labels(default_config, [])
        self.assertListEqual(channels, ['#slak'])
