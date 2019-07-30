import json
import os
import logging
import requests
try:
    from utils.utils import messages
except:
    pass
from telegram.ext import Updater
from telegram import InputFile


class TelegramHandler(object):

    def __init__(self, token, chat_id):
        # ---------------------------------------- #
        # Start the Telegram updater
        self.token = token
        self.chat_id = chat_id
        self.updater = Updater(token=token)
        self.dispatcher = self.updater.dispatcher
        self.bot = self.dispatcher.bot
        self.logger = logging.getLogger(self.__class__.__name__)

        self.last_update_id = 0
        self.get_last_update_id()

    def send_message(self, message):
        self.bot.send_message(chat_id=self.chat_id, text=message)

    def send_image(self, path, caption=None):
        with open(path, "rb") as img:
            self.bot.send_photo(photo=InputFile(img), chat_id=self.chat_id, caption=caption)

    def telegram_api(self, command, **kwargs):
        url = f"https://api.telegram.org/bot{self.token}/{command}?"
        r = requests.post(url, json=kwargs)
        return json.loads(r.content)

    def get_last_update_id(self):
        is_last_update = False
        while not is_last_update:
            r = self.telegram_api("getUpdates", **dict(offset=self.last_update_id))
            if "result" in r and len(r["result"]) > 0:
                is_last_update = int(r["result"][-1]["update_id"]) >= self.last_update_id
                self.last_update_id = int(r["result"][-1]["update_id"])

    def send_poll(self, attacker_name, defender_name):
        question = "some question"

        poll = dict(
            chat_id=self.chat_id,
            question=question,
            options=[attacker_name, defender_name],
            disable_notification=True,
        )
        r = self.telegram_api("sendPoll", **poll)
        if not r["ok"]:
            self.logger.error("Cannot open poll")
            raise RuntimeError("%s: Cannot open poll" % __name__)

        message_id = r["result"]["message_id"]
        poll_id = r["result"]["poll"]["id"]

        self.logger.debug("Poll successfully opened. message_id: %s, poll_id: %s", message_id, poll_id)

        return message_id, poll_id

    def get_poll(self, poll_id):
        r = self.telegram_api("getUpdates", **dict(offset=-1))
        if not r["ok"]:
            self.logger.error("Cannot get poll with poll_id %s", poll_id)
            raise RuntimeError("%s Cannot get poll with poll_id %s" % (__name__, poll_id))
        results = r["result"]
        self.last_update_id = results[-1]["update_id"]

        poll = filter(lambda x: "poll" in x, results)
        poll = filter(lambda x: x["poll"]["id"] == poll_id, poll)
        poll = list(poll)
        if len(poll) > 0:
            self.logger.debug("Successfully got poll with poll_id %s", poll_id)
        else:
            self.logger.warning("Cannot find poll with poll_id %s", poll_id)
        return poll

    def get_last_poll(self, poll_id):
        poll = self.get_poll(poll_id)

        ids = [x["update_id"] for x in poll]

        for update in poll:
            if update["update_id"] == max(ids):
                return update["poll"]

    def get_last_poll_results(self, poll_id):
        poll = self.get_last_poll(poll_id)

        # The poll is empty
        if poll is None:
            self.logger.debug("The poll is empty")
            return None

        if not poll["is_closed"]:
            raise RuntimeError("%s: This poll is not closed" % __name__)

        # Count the results
        results = {}
        total_votes = 0
        for option in poll["options"]:
            results[option["text"]] = option["voter_count"]
            total_votes += option["voter_count"]

        self.logger.debug("%d people voted the poll with poll_id: %s" % (total_votes, poll_id))
        return results

    def stop_poll(self, message_id):
        self.logger.debug("Closing Poll")
        args = dict(chat_id=self.chat_id, message_id=message_id)
        r = self.telegram_api("stopPoll", **args)
        if not r["ok"]:
            self.logger.error("Cannot stop poll with message id %s", message_id)
            raise RuntimeError("%s: Cannot stop poll with message_id %s" % (__name__, message_id))
        self.logger.debug("Successfully closed poll with message_id %s" % message_id)
