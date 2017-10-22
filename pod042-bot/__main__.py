#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной модуль бота.
"""
import logging
import os
import signal
import sys
import tempfile
import traceback

import requests
import telebot
from pkg_resources import resource_stream, resource_listdir
from telebot.types import Message, User

from . import config
from .chat_state import SOUNDBOARD_JOJO, ChatState, SOUNDBOARD_GACHI

"""
Словарь id пользователей.
user.username <-> user.id
"""
users_dict: dict = {}

"""
Словарь состояня чатов.
msg.chat.id <-> ChatState
"""
chat_states: dict = {}

soundboard_jojo_sounds: list = []
soundboard_gachi_sounds: list = []

EXIT_SUCCESS = 0
EXIT_UNKNOWN = -256

log: logging.Logger = None

bot = telebot.TeleBot(config.BOT_TOKEN, num_threads=config.NUM_THREADS)


def is_chat_in_state(chat_msg: Message, state_name: str) -> bool:
    """
    Проверяет состояние указанного чата.

    :param Message chat_msg: сообщение из чата
    :param str state_name: название состояния
    :return: ``True``, если чат в указанном состоянии
    :rtype: bool
    """
    chat_id = chat_msg.chat.id
    if (chat_msg.text is not None) and (not chat_msg.text.startswith("/")):
        return False
    if chat_id in chat_states and chat_states[chat_id].started_request_name == state_name:
        return True
    else:
        return False


@bot.message_handler(commands=["abort", ])
def bot_command_abort(msg: Message):
    """
    Отменяет выполняемую команду.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    if chat_id in chat_states and chat_states[chat_id].started_request_name != "":
        chat_states[chat_id].started_request_name = ""
        bot.send_message(chat_id, "Отменено.")
    else:
        bot.send_message(chat_id, "Я ничем не занят!")


@bot.message_handler(func=lambda msg: is_chat_in_state(msg, SOUNDBOARD_JOJO))
def bot_process_soundboard_jojo(msg: Message):
    """
    Отсылает выбранный звук из `JoJo's Bizarre Adventure`.

    :param msg:
    """
    bot_all_messages(msg)
    sound_name = msg.text[1:]  # strip '/'
    if config.BOT_USERNAME in sound_name:
        sound_name = sound_name.replace("@" + config.BOT_USERNAME, "")  # strip @bot name
    log.debug("Got JOJO soundboard element: {}".format(sound_name))
    if sound_name in soundboard_jojo_sounds:
        bot.send_chat_action(msg.chat.id, "record_audio")
        # bot.send_audio(msg.chat.id, resource_stream(config.JOJO, sound_name + '.mp3'))
        bot.send_voice(msg.chat.id, resource_stream(config.JOJO, sound_name + '.mp3'))
    else:
        bot.send_message(msg.chat.id, "Не нашел такого ау<b>дио</b>!", parse_mode="HTML")


@bot.message_handler(func=lambda msg: is_chat_in_state(msg, SOUNDBOARD_GACHI))
def bot_process_soundboard_gachi(msg: Message):
    """
    Отсылает выбранный звук из `Gachimuchi`.

    :param msg:
    """
    bot_all_messages(msg)
    sound_name = msg.text[1:]  # strip '/'
    if config.BOT_USERNAME in sound_name:
        sound_name = sound_name.replace("@" + config.BOT_USERNAME, "")  # strip @bot name
    log.debug("Got GACHI soundboard element: {}".format(sound_name))
    if sound_name in soundboard_gachi_sounds:
        bot.send_chat_action(msg.chat.id, "record_audio")
        # bot.send_audio(msg.chat.id, resource_stream(config.JOJO, sound_name + '.mp3'))
        bot.send_voice(msg.chat.id, resource_stream(config.GACHI, sound_name + '.mp3'))
    else:
        bot.send_message(msg.chat.id, "Не нашел такого ау<b>дио</b>!", parse_mode="HTML")


@bot.message_handler(commands=["soundboard_jojo", ])
def bot_command_soundboard_jojo(msg: Message):
    """
    JoJo's Bizarre Adventure soundboard

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    chat_states[chat_id] = ChatState(SOUNDBOARD_JOJO)
    sounds_list = ""
    for sound in soundboard_jojo_sounds:
        sounds_list += ("/" + sound + "\n")
    out_msg = "Вошел в режим <b>JoJo's Bizarre Adventure soundboard</b>!\n" \
              "Напиши /abort для выхода.\n\n" \
              "Доступные звуки:\n" \
              "{}".format(sounds_list)
    bot.send_message(msg.chat.id, out_msg, parse_mode="HTML")


@bot.message_handler(commands=["soundboard_gachi", ])
def bot_command_soundboard_gachi(msg: Message):
    """
    Gachimuchi soundboard

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    chat_states[chat_id] = ChatState(SOUNDBOARD_GACHI)
    sounds_list = ""
    for sound in soundboard_gachi_sounds:
        sounds_list += ("/" + sound + "\n")
    out_msg = "Вошел в режим <b>Gachimuchi soundboard</b>!\n" \
              "Напиши /abort для выхода.\n\n" \
              "Доступные звуки:\n" \
              "{}".format(sounds_list)
    bot.send_message(msg.chat.id, out_msg, parse_mode="HTML")


@bot.message_handler(commands=["codfish", ])
def bot_command_codfish(msg: Message):
    """
    Бьет треской, теперь с видео.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    if chat_id in chat_states and chat_states[chat_id].started_request_name != "":
        bot.send_message(chat_id, "Сейчас я занят обработкой комманды <code>{}</code>.\n"
                                  "Для отмены напииши /abort!".format(chat_states[chat_id]
                                                                      .started_request_name),
                         parse_mode="HTML")
        return

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


@bot.message_handler(func=lambda msg: True)
def bot_all_messages(msg: Message):
    """
    Метод для заполнения :var:`users_dict`.
    Обрабатывает любые сообщения.

    :param Message msg: сообщение
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
    Обработчик ``^C``.
    """
    log.info("Exiting...")
    bot.stop_polling()
    sys.exit(EXIT_SUCCESS)


def main() -> int:
    """
    Точка входа.

    :return: код выхода (сейчас не используется)
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

    # Prepare resources
    global soundboard_jojo_sounds
    for file in resource_listdir(config.JOJO, ""):
        if file.endswith(".mp3"):
            soundboard_jojo_sounds.append(file[:-4])  # strip '.mp3'

    global soundboard_gachi_sounds
    for file in resource_listdir(config.GACHI, ""):
        if file.endswith(".mp3"):
            soundboard_gachi_sounds.append(file[:-4])
    log.debug("got jojo sounds: {}".format(soundboard_jojo_sounds))
    log.debug("got gachi sounds: {}".format(soundboard_gachi_sounds))

    log.info("Starting...")
    bot.polling(none_stop=True)
    # Block thread!

    return EXIT_SUCCESS


if __name__ == '__main__':
    """
    Ловит и записывает любое исключение.
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
