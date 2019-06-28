import unittest
import mock
import json

from mention import config
from mention import mention_bot
from mention import notify


class TestNotify(unittest.TestCase):
    def test_create_slack_msg(self):
        with open('tests/data/merge_request_event.json') as f:
            data = json.loads(f.read())
            labels = 'ccgh'
            msg = notify.create_slack_msg_long(data, labels)
            self.assertTrue(len(msg) > 0)

    def test_create_slack_msg_short(self):
        with open('tests/data/merge_request_event.json') as f:
            data = json.loads(f.read())
            labels = ['ccgh']
            msg, _ = notify.create_slack_msg_short(data, labels)
            # self.assertTrue(len(msg) > 0)
            self.assertEqual(
                msg,
                'root opened *!1* in _<http://gitlab/p/higgs/|p/higgs>_: *<http://example.com/diaspora/merge_requests/1|MS-Viewport>* _(`ccgh`)_'
            )

            labels = ''
            msg, _ = notify.create_slack_msg_short(data, labels)
            # self.assertTrue(len(msg) > 0)
            self.assertEqual(
                msg,
                'root opened *!1* in _<http://gitlab/p/higgs/|p/higgs>_: *<http://example.com/diaspora/merge_requests/1|MS-Viewport>* '
            )
