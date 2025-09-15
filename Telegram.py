import html
import json
import logging
import urllib.parse
from configparser import ConfigParser
import time
import os

import requests
from dotenv import load_dotenv


class Telegram:

    def __init__(self):
        load_dotenv()
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.channel = os.getenv("TELEGRAM_CHANNEL")

    def sendMessage(self, message):
        if len(message) > 4096:
            message = message[0:4096]  # limit api 4096 chars

        if self.token is not None and self.channel is not None:

            message = urllib.parse.quote(message)

            url = 'https://api.telegram.org/bot' + self.token + '/sendMessage?chat_id=' + \
                  self.channel + '&text=' + message + '&parse_mode=html&disable_web_page_preview=false'

            result = requests.get(url).json()
            if not result["ok"]:
                logging.error("error sending telegram messages " + str(result))
