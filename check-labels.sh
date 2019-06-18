#!/usr/bin/env bash

cd /usr/local/mention-bot/mention-bot-lfyzjck/

source ve3/bin/activate

PYTHONPATH=. python ./mention/app.py -quick-check

