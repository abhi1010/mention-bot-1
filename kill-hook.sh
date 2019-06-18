#!/usr/bin/env bash

ps -ef  | egrep mention-bot | egrep -v "egrep" | awk '{print $2}' | xargs kill -9
