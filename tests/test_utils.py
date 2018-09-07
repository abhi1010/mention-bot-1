import pytest

import unittest
import mock
import json

from mention import gitlab_client
from mention import app
from mention import config
from mention import mention_bot
from mention import notify


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
        labels = gitlab_client.get_labels(default_config, files)
        self.assertListEqual(labels, sorted(['risk', 'pylib']))

    def test_get_channels_based_on_labels(self):
        default_config = mention_bot.BotConfig.from_dict(
            config.get_default_config())
        channels = gitlab_client.get_channels_based_on_labels(default_config,
                                                              ['ccgh', 'risk'])
        self.assertListEqual(channels, [u'#gitlab-merge-requests'])

        channels = gitlab_client.get_channels_based_on_labels(default_config, [])
        self.assertListEqual(channels, ['#gitlab-merge-requests'])

    def test_get_payload_labels(self):
        payload = {u'labels': [{u'title': u'risk'}, {u'title': u'ccgh'}]}
        labels = gitlab_client.get_payload_labels(payload)
        self.assertListEqual(sorted(labels), ['ccgh', 'risk'])
