#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной модуль бота.
"""
import logging
import os
import random
import re
import signal
import sys
import tempfile
import traceback
import typing

import requests
import telebot
from pkg_resources import resource_stream, resource_listdir
from telebot.types import Message, User
from vk_api import vk_api

try:
    from . import chat_state
    from . import config
    from . import vk_group
except ImportError:
    import chat_state
    import config
    import vk_group

"""
Словарь id пользователей.
user.username <-> user.id
"""
users_dict: dict = {}

"""
Словарь состояня чатов.
msg.chat.id <-> ChatState
"""
chat_states: typing.Dict[int, chat_state.ChatState] = {}

soundboard_jojo_sounds: list = []
soundboard_gachi_sounds: list = []

EXIT_SUCCESS = 0
EXIT_UNKNOWN = -256

log: logging.Logger = None

bot = telebot.TeleBot(config.BOT_TOKEN, num_threads=config.NUM_THREADS)
vk_session = vk_api.VkApi(login=config.VK_LOGIN, password=config.VK_PASSWORD)
vk_session.auth()
vk = vk_session.get_api()


def chat_in_state(chat_msg: Message, state_name: str) -> bool:
    """
    Проверяет состояние указанного чата.

    :param Message chat_msg: сообщение из чата
    :param str state_name: название состояния
    :return: ``True``, если чат в указанном состоянии
    :rtype: bool
    """
    chat_id = chat_msg.chat.id
    if chat_id in chat_states and chat_states[chat_id].state_name == state_name:
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
    if (chat_id in chat_states) and (not chat_in_state(msg, chat_state.NONE)):
        chat_states[chat_id].state_name = chat_state.NONE
        bot.send_message(chat_id, "Отменено.")
    else:
        bot.send_message(chat_id, "Я ничем не занят!")


@bot.message_handler(func=lambda msg: chat_in_state(msg, chat_state.WHATANIME))
def bot_process_whatanime(msg: Message):
    """
    Ищет скриншот из аниме с помощью `whatanime.ga`.

    :param Message msg: сообщение
    """


@bot.message_handler(func=lambda msg: chat_in_state(msg, chat_state.CONFIGURE_VK_GROUPS_ADD))
def bot_process_configuration_vk(msg: Message):
    """
    Проверяет адреса и добавляет их в список групп ВК.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    this_chat: chat_state.ChatState = chat_states[msg.chat.id]
    if (msg.reply_to_message is not None and this_chat.message_id_to_reply is not None) \
            and (msg.reply_to_message.message_id == this_chat.message_id_to_reply):
        text: str = msg.text
        group_name_regex = re.compile(r".*vk\.com/(.+?)(\?.+)?$", re.MULTILINE)
        dead_links: list = []
        vk_groups = this_chat.vk_groups
        for line in text.splitlines():
            log.debug("line {}".format(line))
            if not group_name_regex.match(line):
                dead_links.append(line)
                break
            group_name: str = re.sub(group_name_regex, r"\1", line)
            log.info("got group \"{}\"...".format(group_name))
            try:
                response = vk.groups.getById(group_id=group_name, fields="id", version=5.68)
            except (vk_api.ApiError, vk_api.ApiHttpError) as err:
                log.warning("...but request failed ({})".format(err))
                dead_links.append(line)
                break
            log.debug("...and vk response:\n"
                      "{}".format(response))
            group_dict: dict = response[0]
            group = vk_group.VkGroup(group_dict["id"], group_dict["name"], group_dict["screen_name"])
            log.info("finally, our group: {}".format(group))
            vk_groups.append(group)

        success_grps = ""
        for entry in vk_groups:
            success_grps += entry.__str__() + "\n"

        fail_grps = ""
        for entry in dead_links:
            fail_grps += entry + "\n"

        out_msg = "<b>Попытка добавления!</b>\n" \
                  "Для остановки напиши /abort\n\n" \
                  "Сейчас в списке:\n" \
                  "<code>{}</code>\n" \
                  "Не добавлено:\n" \
                  "<code>{}</code>".format(success_grps, fail_grps)
        bot.send_message(msg.chat.id, out_msg, parse_mode="HTML")


@bot.message_handler(func=lambda msg: chat_in_state(msg, chat_state.SOUNDBOARD_JOJO) and msg.text.startswith("/"))
def bot_process_soundboard_jojo(msg: Message):
    """
    Отсылает выбранный звук из `JoJo's Bizarre Adventure`.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    sound_name = msg.text[1:]  # strip '/'
    if config.BOT_USERNAME in sound_name:
        sound_name = sound_name.replace("@" + config.BOT_USERNAME, "")  # strip @bot name
    log.debug("Got JOJO soundboard element: {}".format(sound_name))
    if sound_name in soundboard_jojo_sounds:
        bot.send_chat_action(msg.chat.id, "record_audio")
        bot.send_voice(msg.chat.id, resource_stream(config.JOJO, sound_name + '.mp3'))
    else:
        bot.send_message(msg.chat.id, "Не нашел такого ау<b>дио</b>!", parse_mode="HTML")


@bot.message_handler(func=lambda msg: chat_in_state(msg, chat_state.SOUNDBOARD_GACHI) and msg.text.startswith("/"))
def bot_process_soundboard_gachi(msg: Message):
    """
    Отсылает выбранный звук из `Gachimuchi`.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    sound_name = msg.text[1:]  # strip '/'
    if config.BOT_USERNAME in sound_name:
        sound_name = sound_name.replace("@" + config.BOT_USERNAME, "")  # strip @bot name
    log.debug("Got GACHI soundboard element: {}".format(sound_name))
    if sound_name in soundboard_gachi_sounds:
        bot.send_chat_action(msg.chat.id, "record_audio")
        bot.send_voice(msg.chat.id, resource_stream(config.GACHI, sound_name + '.mp3'))
    else:
        bot.send_message(msg.chat.id, "Не нашел такого ау<b>дио</b>!", parse_mode="HTML")


@bot.message_handler(commands=['add', ])
def bot_command_configuration_vk_add(msg: Message):
    """
    Переводит бота в режим добавления групп ВК, если находится в правильном состоянии.

    :param Message msg: сообщение
    """
    if chat_in_state(msg, chat_state.CONFIGURE_VK_GROUPS):
        out_msg = "<b>Reply`ем на это сообщение</b> напишите адреса <b>публичных</b> сообществ ВК, " \
                  "по одному на строку.\n" \
                  "<i>Желательно без мусорных знаков...</i>"
        chat_id = msg.chat.id
        sent_msg = bot.send_message(chat_id, out_msg, parse_mode="HTML")
        if chat_id in chat_states:
            chat_states[chat_id].state_name = chat_state.CONFIGURE_VK_GROUPS_ADD
            chat_states[chat_id].message_id_to_reply = sent_msg.message_id
        else:
            chat_states[chat_id] = chat_state.ChatState(chat_state.CONFIGURE_VK_GROUPS_ADD, sent_msg.message_id)


@bot.message_handler(commands=["clear", ])
def bot_command_configuration_vk_clear(msg: Message):
    """
    Очищает список групп ВК, если находится в правильном состоянии.

    :param Message msg: сообщение
    """
    if chat_in_state(msg, chat_state.CONFIGURE_VK_GROUPS):
        chat_id = msg.chat.id
        if chat_id in chat_states:
            chat_states[chat_id].vk_groups.clear()
            chat_states[chat_id].state_name = chat_state.NONE
            bot.send_message(chat_id, "Выполнено, вернулся в основной режим.")


@bot.message_handler(commands=["config_vk", ])
def bot_command_configuration_vk(msg: Message):
    """
    Запускает настройку сообществ `vk.com`.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    grps_str = ""
    if chat_id in chat_states:
        chat_states[chat_id].state_name = chat_state.CONFIGURE_VK_GROUPS
        grps = chat_states[chat_id].vk_groups
        for entry in grps:
            grps_str += entry.__str__() + "\n"
    else:
        chat_states[chat_id] = chat_state.ChatState(chat_state.CONFIGURE_VK_GROUPS)

    out_msg = "Вошел в режим <b>Конфигурация модуля ВКонтакте</b>!\n" \
              "/add — добавление групп\n" \
              "/clear — очистка списка\n" \
              "/abort — отмена\n\n" \
              "Сейчас в списке:\n" \
              "<code>{}</code>\n".format(grps_str)
    bot.send_message(chat_id, out_msg, parse_mode="HTML")


@bot.message_handler(commands=["vk_pic", ])
def bot_command_vk_pic(msg: Message):
    """
    Посылает рандомную картинку из списка сообществ.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    if (chat_id not in chat_states) or (len(chat_states[chat_id].vk_groups) == 0):
        bot.send_message(chat_id, "Сначала настройте группы с помощью /config_vk")
        return
    chosen_group: vk_group.VkGroup = random.choice(chat_states[chat_id].vk_groups)
    log.debug("selected {} as source".format(chosen_group))
    response = vk.wall.get(domain=chosen_group.url_name, count=100, fields="attachments", version=5.68)
    photo_attach_regex = re.compile(r"photo_(\d+)")
    max_size_url = "ERROR"
    chosen = False
    while not chosen:
        chosen_post: dict = random.choice(response["items"])
        log.debug("chosen {}!".format(chosen_post))
        if chosen_post["marked_as_ads"] == 1:
            chosen = False
            log.debug("skip (ad)")
            continue
        if "attachments" not in chosen_post:
            chosen = False
            log.debug("skip (attach)")
            continue
        for attach in chosen_post["attachments"]:
            if "photo" in attach:
                log.info("found!")
                photo_attach = attach["photo"]
                log.info("attach {}".format(photo_attach))
                max_size = 75
                for key in photo_attach:
                    value = photo_attach[key]
                    log.debug("<{}> -> {}".format(key, value))
                    if photo_attach_regex.match(key):
                        size = int(re.sub(photo_attach_regex, r"\1", key))
                        if size > max_size:
                            max_size = size
                max_size_url = photo_attach["photo_" + str(max_size)]
                chosen = True
                break
    bot.send_message(chat_id, "{}\n"
                              "Из https://vk.com/{}".format(max_size_url, chosen_group.url_name))


@bot.message_handler(commands=["soundboard_jojo", ])
def bot_command_soundboard_jojo(msg: Message):
    """
    JoJo's Bizarre Adventure soundboard

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    if chat_id in chat_states:
        chat_states[chat_id].state_name = chat_state.SOUNDBOARD_JOJO
    else:
        chat_states[chat_id] = chat_state.ChatState(chat_state.SOUNDBOARD_JOJO)
    sounds_list = ""
    for sound in soundboard_jojo_sounds:
        sounds_list += ("/" + sound + "\n")
    out_msg = "Вошел в режим <b>JoJo's Bizarre Adventure soundboard</b>!\n" \
              "Напиши /abort для выхода.\n\n" \
              "Доступные звуки:\n" \
              "{}".format(sounds_list)
    bot.send_message(chat_id, out_msg, parse_mode="HTML")


@bot.message_handler(commands=["soundboard_gachi", ])
def bot_command_soundboard_gachi(msg: Message):
    """
    Gachimuchi soundboard

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    if chat_id in chat_states:
        chat_states[chat_id].state_name = chat_state.SOUNDBOARD_GACHI
    else:
        chat_states[chat_id] = chat_state.ChatState(chat_state.SOUNDBOARD_GACHI)
    sounds_list = ""
    for sound in soundboard_gachi_sounds:
        sounds_list += ("/" + sound + "\n")
    out_msg = "Вошел в режим <b>Gachimuchi soundboard</b>!\n" \
              "Напиши /abort для выхода.\n\n" \
              "Доступные звуки:\n" \
              "{}".format(sounds_list)
    bot.send_message(chat_id, out_msg, parse_mode="HTML")


@bot.message_handler(commands=["whatanime", ])
def bot_command_whatanime(msg: Message):
    """
    Входит в режим поиска аниме по скриншоту (спасибо whatanime.ga за API)

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    if chat_id in chat_states:
        chat_states[chat_id].state_name = chat_state.WHATANIME
        chat_states[chat_id].message_id_to_reply = msg.message_id
    else:
        chat_states[chat_id] = chat_state.ChatState(chat_state.WHATANIME, message_id_to_reply=msg.message_id)
    out_msg = "Вошел в режим <b>whatanime.ga: поиск аниме</b>!\n" \
              "Напиши /abort для выхода.\n\n" \
              "Для поиска <b>Reply</b>`ни на это сообщение с картинкой или ссылкой (WIP)."
    bot.send_message(chat_id, out_msg, parse_mode="HTML")


@bot.message_handler(commands=["codfish", ])
def bot_command_codfish(msg: Message):
    """
    Бьет треской, теперь с видео.

    :param Message msg: сообщение
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
        response_json: tuple = raw.json()
        # noinspection PyTypeChecker
        user_first_name = response_json["result"]["user"]["first_name"]
        log.debug("user first name is {}".format(user_first_name))
        bot.send_video(chat_id, codfish_video, caption="Хорошенько шлепнул {} треской."
                       .format(user_first_name))
    else:  # Unknown
        bot.send_message(chat_id, "Извини, пока не знаю <b>{}</b>...".format(username), parse_mode="HTML")


@bot.message_handler(commands=["quote", ])
def bot_command_quote(msg: Message):
    """
    Посылает рандомную цитату с `tproger.ru`.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    quote = requests.get("https://tproger.ru/wp-content/plugins/citation-widget/getQuotes.php").text
    bot.send_message(msg.chat.id, "<code>{}</code>".format(quote), parse_mode="HTML")


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

    log.info("init vk test...")
    response = vk.groups.getById(group_id="team", fields="id", version=5.68)
    log.info("success! response:\n\t{}".format(response))

    log.info("Starting...")
    bot.polling(none_stop=True)
    # Block thread!

    return EXIT_SUCCESS


if __name__ == '__main__':
    """
    Ловит и записывает любое исключение.
    """
    print("init!")
    signal.signal(signal.SIGINT, exit_handler)
    while True:
        # noinspection PyBroadException
        try:
            sys.exit(main())  # Return exit code to shell
            # main()
        except Exception as e:
            print("Unknown exception was raised!\n"
                  "{}".format(traceback.format_exc()))
            # bot = telebot.TeleBot(config.BOT_TOKEN, num_threads=config.NUM_THREADS)
            sys.exit(EXIT_UNKNOWN)
