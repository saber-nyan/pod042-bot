#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main bot module.
"""
import logging
import os
import signal
import sys
import tempfile
import traceback

import requests
import telebot
from telebot.types import Message, User
from pkg_resources import resource_stream

from . import config

"""
User id's dictionary.
user.username <-> user.id
"""
users_dict = {}

EXIT_SUCCESS = 0
EXIT_UNKNOWN = -256

log: logging.Logger = None

bot = telebot.TeleBot(config.BOT_TOKEN, num_threads=config.NUM_THREADS)


@bot.message_handler(commands=["codfish", ])
def bot_command_codfish(msg: Message):
    """
    Method for hitting with cod.

    :param msg: original message
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id

    text = msg.text.replace("@", "")  # Sometimes `lolbot` is written as `@lolbot`
    words = text.split()
    username = words[-1]  # Get username from orig. message
    bot.send_chat_action(chat_id, "record_video")
    codfish_video = resource_stream(config.VIDEOS, config.CODFISH)  # Our codfish video
    if len(words) <= 1:  # No username
        bot.send_message(chat_id, "Укажи юзернейм кого бить!")
    elif username == config.BOT_USERNAME:  # Himself
        bot.send_video(chat_id, codfish_video, caption="Хорошенько шлепнул себя треской.")
    elif username in users_dict:  # Search in our users dict (user_id's are unique?)
        raw = requests.get("https://api.telegram.org:443/bot{}/getChatMember?chat_id={}&user_id={}"
                           .format(config.BOT_TOKEN, chat_id, users_dict[username]))  # Get user first name
        json: tuple = raw.json()
        # noinspection PyTypeChecker
        user_first_name = json["result"]["user"]["first_name"]
        log.debug("user first name is {}".format(user_first_name))
        bot.send_video(chat_id, codfish_video, caption="Хорошенько шлепнул {} треской."
                       .format(user_first_name))
    else:  # Unknown
        bot.send_message(chat_id, "Извини, пока не знаю <b>{}</b>...".format(username), parse_mode="HTML")


@bot.message_handler(func=lambda m: True)
def bot_all_messages(msg: Message):
    """
    Method for filling users dictionary; handles every msg from anyone.

    :param msg: original message
    """
    user: User = msg.from_user
    if user.username not in users_dict:
        log.debug("user not known")
        users_dict[user.username] = user.id
    else:
        log.debug("user known")


# noinspection PyUnusedLocal
def exit_handler(sig, frame):
    """
    Interrupt (^C) handler.
    """
    log.info("Exiting...")
    bot.stop_polling()
    sys.exit(EXIT_SUCCESS)


def main() -> int:
    """
    Main function.

    :return: exit code
    :rtype: int
    """
    formatter = logging.Formatter(config.LOG_FORMAT)
    loglevel = config.LOG_LEVEL
    global log
    log = logging.getLogger()
    log.setLevel(loglevel)
    fh = logging.FileHandler(os.path.join(tempfile.gettempdir(), "pod042_bot.log"))
    fh.setFormatter(formatter)
    fh.setLevel(loglevel)
    if config.LOG_TO_FILE:
        log.addHandler(fh)
        log.info("Logs path: {}".format(tempfile.gettempdir()))
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(loglevel)
    if config.LOG_TO_STDOUT:
        log.addHandler(ch)

    log.info("Starting...")
    bot.polling(none_stop=True)
    # Block thread!

    return EXIT_SUCCESS


if __name__ == '__main__':
    """
    Catches & reports any exception.
    """
    signal.signal(signal.SIGINT, exit_handler)
    while True:
        # noinspection PyBroadException
        try:
            # sys.exit(main())  # Return exit code to shell
            main()
        except Exception as e:
            print("Unknown exception was raised!\n"
                  "{}".format(traceback.format_exc()))
            bot = telebot.TeleBot(config.BOT_TOKEN, num_threads=config.NUM_THREADS)
            # sys.exit(EXIT_UNKNOWN)  Nope, keep going.
