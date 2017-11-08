#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной модуль бота.
"""
import io
import logging
import os
import pickle
import random
import re
import signal
import sys
import traceback
import typing
from datetime import datetime
from pathlib import Path

import requests
import telebot
from pkg_resources import resource_stream, resource_listdir
from telebot.types import Message, User, Chat, PhotoSize, File, Document, ForceReply
from vk_api import vk_api, VkTools
from vk_api.vk_api import VkApiMethod

try:
    from . import chat_state
    from . import config
    from . import vk_group
    from . import whatanime_ga
except ImportError:
    import chat_state
    import config
    import vk_group
    import whatanime_ga

users_dict: typing.Dict[str, int] = {}
"""
Словарь id пользователей.
user.username <-> user.id
"""

chat_states: typing.Dict[int, chat_state.ChatState] = {}
"""
Словарь состояня чатов.
msg.chat.id <-> ChatState
"""

soundboard_jojo_sounds: list = []
soundboard_gachi_sounds: list = []

messages_log_files: typing.Dict[int, io.StringIO] = {}
"""
Словарь файлов для полного логгирования чатов.
msg.chat.id <-> file stream (io.StringIO)
"""

log: logging.Logger = None

root_path = os.path.join(Path.home(), ".pod042-bot")

bot = telebot.TeleBot(config.BOT_TOKEN, num_threads=config.NUM_THREADS)
whatanime: whatanime_ga.WhatAnimeClient = None
whatanime_disabled = True
vk: VkApiMethod = None
vk_tools: VkTools = None
vk_disabled = True

VK_VER = 5.69

VK_PHOTO_ATTACH_REGEX = re.compile(r"photo_(\d+)")
VK_GROUP_REGEX = re.compile(r".*vk\.com/(.+?)(\?.+)?$", re.MULTILINE)
HTML_ANEK_REGEX = re.compile(r"<meta name=\"description\" content=\"(.*?)\">", re.DOTALL)

EXIT_SUCCESS = 0
EXIT_UNKNOWN = -256


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
def bot_cmd_abort(msg: Message):
    """
    Отменяет выполняемую команду.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    if not chat_in_state(msg, chat_state.NONE):
        chat_states[chat_id].state_name = chat_state.NONE
        bot.send_message(chat_id, "Отменено.")
    else:
        bot.send_message(chat_id, "Я ничем не занят!")


@bot.message_handler(commands=["info", ])
def bot_cmd_info(msg: Message):
    """
    Информация о боте и чате.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    # TODO


@bot.message_handler(func=lambda msg: chat_in_state(msg, chat_state.WHATANIME),
                     content_types=["text", "document", "photo"])
def bot_process_whatanime(msg: Message):
    """
    Ищет скриншот из аниме с помощью `whatanime.ga`.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    msg_text = msg.text

    if (msg.photo is None and msg.document is None) and not msg_text.startswith(("http://", "https://",)):
        log.debug("not link, skipping: {}".format(msg.text))
        return

    ready = "\u2705 "
    pending = "\u2747\ufe0f "
    not_ready = "\u274e "
    error = "\u203c\ufe0f "

    # Prepare URL
    status_msg = bot.send_message(chat_id, pending + "Подготовка ссылки\n" +
                                  not_ready + "Загрузка\n" +
                                  not_ready + "Поиск\n" +
                                  not_ready + "Результат\n" +
                                  not_ready + "Превью\n")
    if msg.photo is not None:  # Фото, .jpg
        photos: typing.List[PhotoSize] = msg.photo
        file: File = bot.get_file(photos[-1].file_id)  # Biggest resolution
        download_url = "https://api.telegram.org/file/bot{}/{}".format(config.BOT_TOKEN, file.file_path)
        log.debug("pic")
    elif msg.document is not None:  # Документ, any!
        document: Document = msg.document
        file: File = bot.get_file(document.file_id)
        download_url = "https://api.telegram.org/file/bot{}/{}".format(config.BOT_TOKEN, file.file_path)
        log.debug("doc")
    else:  # Ссылка, any!
        download_url = msg_text
        log.debug("text")
    if download_url is None:
        bot.edit_message_text(error + "Подготовка ссылки\n" +
                              not_ready + "Загрузка\n" +
                              not_ready + "Поиск\n" +
                              not_ready + "Результат\n" +
                              not_ready + "Превью\n",
                              chat_id, status_msg.message_id)
        bot.send_message(chat_id, "Не смог получить ссылку для загрузки. Жду еще одного сообщения или /abort!")
        return
    log.debug("ready to download input, url: {}".format(download_url))

    # Download!
    try:
        status_msg = bot.edit_message_text(ready + "Подготовка ссылки\n" +
                                           pending + "Загрузка\n" +
                                           not_ready + "Поиск\n" +
                                           not_ready + "Результат\n" +
                                           not_ready + "Превью\n",
                                           chat_id, status_msg.message_id)
        response = requests.get(download_url, timeout=5, stream=True)
        data = response.raw.read(2097152 + 1, decode_content=True)
        if len(data) > 2097152:  # 2MB
            response.close()
            bot.edit_message_text(ready + "Подготовка ссылки\n" +
                                  error + "Загрузка\n" +
                                  not_ready + "Поиск\n" +
                                  not_ready + "Результат\n" +
                                  not_ready + "Превью\n",
                                  chat_id, status_msg.message_id)
            bot.send_message(chat_id, "Объем данных превышает 2МБ, отменено. Жду еще одного сообщения или /abort!")
            return
        search_file_path = os.path.join(root_path, "search_{}".format(msg.message_id))
        with open(search_file_path, mode="wb") as file:
            file.write(data)
    except Exception as exc:
        bot.edit_message_text(ready + "Подготовка ссылки\n" +
                              error + "Загрузка\n" +
                              not_ready + "Поиск\n" +
                              not_ready + "Результат\n" +
                              not_ready + "Превью\n",
                              chat_id, status_msg.message_id)
        bot.send_message(chat_id, "Ошибка при загрузке. Жду еще одного сообщения или /abort!\n"
                                  "Подробнее: {}".format(exc))
        log.debug("{}".format(traceback.format_exc()))
        # noinspection PyBroadException
        try:
            # noinspection PyUnboundLocalVariable
            os.remove(os.path.realpath(search_file_path))
        except:
            pass
        return

    status_msg = bot.edit_message_text(ready + "Подготовка ссылки\n" +
                                       ready + "Загрузка\n" +
                                       pending + "Поиск\n" +
                                       not_ready + "Результат\n" +
                                       not_ready + "Превью\n",
                                       chat_id, status_msg.message_id)
    # Search!
    try:
        results: typing.List[whatanime_ga.WhatAnimeResult] = whatanime.search(search_file_path)
        status_msg = bot.edit_message_text(ready + "Подготовка ссылки\n" +
                                           ready + "Загрузка\n" +
                                           ready + "Поиск\n" +
                                           pending + "Результат\n" +
                                           not_ready + "Превью\n",
                                           chat_id, status_msg.message_id)
        # Вообще-то, результатов обычно несколько. Но мне слишком лень писать сложную обработку, поэтому довольствуемся
        # самым подходящим.
        result = results[0]
        result.load_thumbnail()
        bot.send_message(chat_id, "<code>{}</code>".format(result.title_romaji), parse_mode="HTML")
        status_msg = bot.edit_message_text(ready + "Подготовка ссылки\n" +
                                           ready + "Загрузка\n" +
                                           ready + "Поиск\n" +
                                           ready + "Результат\n" +
                                           pending + "Превью\n"
                                                     "Осталось {} запросов за {} секунд."
                                           .format(whatanime.now_quota,
                                                   whatanime.quota_expire),
                                           chat_id, status_msg.message_id)
        match = "Совпадение" if result.similarity > 0.80 else "Низкая вероятность! Совпадение"
        out_msg = "{0}: {1:.1f}%\n" \
                  "{2} (EP#{3}, в {4:.2f} мин)\n" \
                  "{5}".format(match, result.similarity * 100, result.title, result.episode,
                               result.at / 60, result.title_english)
        with open(result.thumb_path, mode="rb") as file:
            bot.send_photo(chat_id, file, out_msg)
        os.remove(result.thumb_path)
    except Exception as exc:
        bot.edit_message_text(ready + "Подготовка ссылки\n" +
                              ready + "Загрузка\n" +
                              error + "Поиск\n" +
                              not_ready + "Результат\n" +
                              not_ready + "Превью\n",
                              chat_id, status_msg.message_id)
        bot.send_message(chat_id, "Ошибка при поиске. Жду еще одного сообщения или /abort!\n"
                                  "Подробнее: {}".format(exc))
        log.debug("{}".format(traceback.format_exc()))
        os.remove(os.path.realpath(search_file_path))
        return

    # Preview!
    try:
        result.load_preview()
        out_msg = "{0:.2f} - {1:.2f}".format(result.__dict__["from"] / 60, result.to / 60)
        bot.send_chat_action(chat_id, "record_video")
        with open(result.preview_path, mode="rb") as file:
            bot.send_video(chat_id, file, caption=out_msg)
        os.remove(result.preview_path)
        bot.edit_message_text(ready + "Подготовка ссылки\n" +
                              ready + "Загрузка\n" +
                              ready + "Поиск\n" +
                              ready + "Результат\n" +
                              ready + "Превью\n"
                                      "Осталось {} запросов за {} секунд."
                              .format(whatanime.now_quota, whatanime.quota_expire),
                              chat_id, status_msg.message_id)
    except Exception as exc:
        bot.edit_message_text(ready + "Подготовка ссылки\n" +
                              ready + "Загрузка\n" +
                              ready + "Поиск\n" +
                              ready + "Результат\n" +
                              error + "Превью ({})\n"
                                      "Осталось {} запросов за {} секунд."
                              .format(exc, whatanime.now_quota, whatanime.quota_expire),
                              chat_id, status_msg.message_id)
        log.debug("{}".format(traceback.format_exc()))

    os.remove(os.path.realpath(search_file_path))
    chat_states[chat_id].state_name = chat_state.NONE


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
        dead_links: list = []
        vk_groups = this_chat.vk_groups
        for line in text.splitlines():
            log.debug("line {}".format(line))
            if not VK_GROUP_REGEX.match(line):
                dead_links.append(line)
                break
            group_name: str = re.sub(VK_GROUP_REGEX, r"\1", line)
            log.debug("got group \"{}\"...".format(group_name))
            try:
                response = vk.groups.getById(group_id=group_name, fields="id", version=VK_VER)
            except (vk_api.ApiError, vk_api.ApiHttpError) as err:
                log.info("...but request failed ({})".format(err))
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
                  "<code>{}</code>".format(success_grps, fail_grps if (len(fail_grps) != 0) else "Ничего!")
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
def bot_cmd_configuration_vk_add(msg: Message):
    """
    Переводит бота в режим добавления групп ВК, если находится в правильном состоянии.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    if chat_in_state(msg, chat_state.CONFIGURE_VK_GROUPS):
        out_msg = "<b>Reply`ем на это сообщение</b> напишите адреса <b>публичных</b> сообществ ВК, " \
                  "по одному на строку.\n" \
                  "<i>Желательно без мусорных знаков...</i>"
        chat_id = msg.chat.id
        sent_msg = bot.send_message(chat_id, out_msg, reply_markup=ForceReply(), parse_mode="HTML")
        chat_states[chat_id].state_name = chat_state.CONFIGURE_VK_GROUPS_ADD
        chat_states[chat_id].message_id_to_reply = sent_msg.message_id


@bot.message_handler(commands=["clear", ])
def bot_cmd_configuration_vk_clear(msg: Message):
    """
    Очищает список групп ВК, если находится в правильном состоянии.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    if chat_in_state(msg, chat_state.CONFIGURE_VK_GROUPS):
        chat_id = msg.chat.id
        chat_states[chat_id].vk_groups.clear()
        bot.send_message(chat_id, "Выполнено.")


@bot.message_handler(commands=["config_vk", ])
def bot_cmd_configuration_vk(msg: Message):
    """
    Запускает настройку сообществ `vk.com`.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    if vk_disabled:
        bot.send_message(chat_id, "Модуль ВКонтакте отключен.")
        return
    grps_str = ""
    chat_states[chat_id].state_name = chat_state.CONFIGURE_VK_GROUPS
    grps = chat_states[chat_id].vk_groups
    for entry in grps:
        grps_str += entry.__str__() + "\n"

    out_msg = "Вошел в режим <b>Конфигурация модуля ВКонтакте</b>!\n" \
              "/add — добавление групп\n" \
              "/clear — очистка списка\n" \
              "/abort — отмена\n\n" \
              "Сейчас в списке:\n" \
              "<code>{}</code>\n".format(grps_str)
    bot.send_message(chat_id, out_msg, parse_mode="HTML")


@bot.message_handler(commands=["vk_pic", ])
def bot_cmd_vk_pic(msg: Message):
    """
    Посылает рандомную картинку из списка сообществ.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    if vk_disabled:
        bot.send_message(chat_id, "Модуль ВКонтакте отключен.")
        return
    if len(chat_states[chat_id].vk_groups) == 0:
        bot.send_message(chat_id, "Сначала настройте группы с помощью /config_vk")
        return
    bot.send_chat_action(chat_id, "upload_photo")
    chosen_group: vk_group.VkGroup = random.choice(chat_states[chat_id].vk_groups)
    log.debug("selected {} as source".format(chosen_group))
    response = vk_tools.get_all("wall.get", max_count=config.VK_ITEMS_PER_REQUEST, values={
        "domain": chosen_group.url_name,
        "fields": "attachments",
        "version": VK_VER,
    }, limit=config.VK_ITEMS_PER_REQUEST * 25)  # 275 постов по умолчанию
    max_size_url = "ERROR"
    log.debug("items count: {}".format(len(response["items"])))
    chosen = False
    while not chosen:
        chosen_post: dict = random.choice(response["items"])
        if chosen_post["marked_as_ads"] == 1:
            log.debug("skip (ad)")
            continue
        if "attachments" not in chosen_post:
            log.debug("skip (attach)")
            continue
        for attach in chosen_post["attachments"]:
            if "photo" in attach:
                log.debug("found photo!")
                photo_attach = attach["photo"]
                log.debug("attach {}".format(photo_attach))
                max_size = 75
                for key in photo_attach:  # Аццкий костыль для выбора фото максимального разрешения
                    value = photo_attach[key]
                    log.debug("<{}> -> {}".format(key, value))
                    if VK_PHOTO_ATTACH_REGEX.match(key):  # Ключ типа ``photo_<res>``, где 25 <= <res> <= inf
                        size = int(re.sub(VK_PHOTO_ATTACH_REGEX, r"\1", key))
                        if size > max_size:
                            max_size = size
                max_size_url = photo_attach["photo_" + str(max_size)]
                chosen = True
                break
            elif "doc" in attach:
                log.debug("photo not found, found doc!")
                doc_attach = attach["doc"]
                if doc_attach["ext"] != "gif":
                    log.debug("but it isn\'t gif...")
                    continue
                max_size_url = doc_attach["url"]
                chosen = True
                break
            else:
                log.debug("not found!")

    bot.send_message(chat_id, "{}\n"
                              "Из https://vk.com/{}".format(max_size_url, chosen_group.url_name))


@bot.message_handler(commands=["soundboard_jojo", ])
def bot_cmd_soundboard_jojo(msg: Message):
    """
    JoJo's Bizarre Adventure soundboard

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    chat_states[chat_id].state_name = chat_state.SOUNDBOARD_JOJO
    sounds_list = ""
    for sound in soundboard_jojo_sounds:
        sounds_list += ("/" + sound + "\n")
    out_msg = "Вошел в режим <b>JoJo's Bizarre Adventure soundboard</b>!\n" \
              "Напиши /abort для выхода.\n\n" \
              "Доступные звуки:\n" \
              "{}".format(sounds_list)
    bot.send_message(chat_id, out_msg, parse_mode="HTML")


@bot.message_handler(commands=["soundboard_gachi", ])
def bot_cmd_soundboard_gachi(msg: Message):
    """
    Gachimuchi soundboard

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    chat_states[chat_id].state_name = chat_state.SOUNDBOARD_GACHI
    sounds_list = ""
    for sound in soundboard_gachi_sounds:
        sounds_list += ("/" + sound + "\n")
    out_msg = "Вошел в режим <b>Gachimuchi soundboard</b>!\n" \
              "Напиши /abort для выхода.\n\n" \
              "Доступные звуки:\n" \
              "{}".format(sounds_list)
    bot.send_message(chat_id, out_msg, parse_mode="HTML")


@bot.message_handler(commands=["whatanime", ])
def bot_cmd_whatanime(msg: Message):
    """
    Входит в режим поиска аниме по скриншоту (спасибо whatanime.ga за API)

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    if whatanime_disabled:
        bot.send_message(chat_id, "Модуль whatanime.ga отключен.")
        return
    chat_states[chat_id].state_name = chat_state.WHATANIME
    chat_states[chat_id].message_id_to_reply = msg.message_id
    out_msg = "Вошел в режим <b>whatanime.ga: поиск аниме</b>!\n" \
              "Напиши /abort для выхода.\n\n" \
              "Для поиска отправь картинку или <b>прямую</b> ссылку (должна начинаться с http/https)."
    bot.send_message(chat_id, out_msg, parse_mode="HTML")


@bot.message_handler(commands=["codfish", ])
def bot_cmd_codfish(msg: Message):
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
def bot_cmd_quote(msg: Message):
    """
    Посылает рандомную цитату с `tproger.ru`.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    quote = requests.get("https://tproger.ru/wp-content/plugins/citation-widget/getQuotes.php").text
    bot.send_message(msg.chat.id, "<code>{}</code>".format(quote), parse_mode="HTML")


@bot.message_handler(commands=["anek", ])
def bot_cmd_anek(msg: Message):
    """
    Посылает рандомный анекдот с `baneks.ru`.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    request = requests.get("https://baneks.ru/{}".format(random.randrange(1, 1142)))
    request.encoding = "utf-8"
    html_text = request.text

    # Да, это парсинг регексами: сервер отдает данные без экранирования кавычек...
    result = HTML_ANEK_REGEX.search(html_text)
    out_msg = result.group(1) if result else "ERROR"
    bot.send_message(msg.chat.id, "<code>{}</code>".format(out_msg), parse_mode="HTML")


@bot.message_handler(func=lambda msg: True,
                     content_types=["text", "audio", "document", "photo", "sticker", "video", "video_note", "voice",
                                    "location", "contact", "new_chat_members", "left_chat_member", "new_chat_title",
                                    "new_chat_photo", "delete_chat_photo", "group_chat_created",
                                    "supergroup_chat_created", "channel_chat_created", "migrate_to_chat_id",
                                    "migrate_from_chat_id", "pinned_message", ])
def bot_all_messages(msg: Message):
    """
    Метод для заполнения :var:`users_dict` и инициализации состояния чатов.
    Обрабатывает любые сообщения.

    :param Message msg: сообщение
    """
    user: User = msg.from_user
    chat: Chat = msg.chat
    if user.username not in users_dict:
        log.debug("user not known")
        users_dict[user.username] = user.id
    else:
        log.debug("user known")
    chat_id = msg.chat.id
    if chat_id not in chat_states:
        log.debug("chat not known")
        chat_states[chat_id] = chat_state.ChatState(chat_state.NONE)
    else:
        log.debug("chat known")
    if config.LOG_INPUT:
        global messages_log_files
        if chat_id not in messages_log_files:
            base_name = "chat_{}.log".format(chat.title if chat.title is not None else chat.username)
            log_path = os.path.join(root_path, base_name)
            messages_log_files[chat_id] \
                = open(log_path, mode="at", buffering=1, encoding="utf-8", errors="backslashreplace")
        file_instance: io.StringIO = messages_log_files[chat_id]
        dtime = datetime.fromtimestamp(msg.date).strftime('%Y-%m-%d %H:%M:%S')
        if msg.text is not None:
            out_str = "({}) {}:\n" \
                      "{}\n\n".format(dtime, user.username, msg.text)
        else:
            out_str = "({}) {}:\n" \
                      "*{}* {}\n\n".format(dtime, user.username, msg.content_type, msg.caption)
        file_instance.write(out_str)
        file_instance.flush()


def prepare_logger() -> logging.Logger:
    """
    Готовит логгер к использованию.

    :return: готовый экземпляр логгера
    :rtype: logging.Logger
    """
    formatter = logging.Formatter(config.LOG_FORMAT)
    loglevel = config.LOG_LEVEL
    l_log = logging.getLogger()
    l_log.setLevel(loglevel)
    if config.LOG_TO_STDOUT:
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        ch.setLevel(loglevel)
        l_log.addHandler(ch)
    if config.LOG_TO_FILE:
        fh = logging.FileHandler(os.path.join(root_path, "main.log"))
        fh.setFormatter(formatter)
        fh.setLevel(loglevel)
        l_log.addHandler(fh)
        l_log.info("Logs path: {}".format(os.path.join(root_path, "main.log")))
    return l_log


def save_chat_states():
    """
    Сохряняет состояние чатов и пользователей в ``.pkl``-файл.
    """
    states_save_path = os.path.join(root_path, "states.pkl")
    users_save_path = os.path.join(root_path, "users.pkl")
    global log
    if log is None:
        log = prepare_logger()
    log.info("saving info to {}...".format(root_path))
    try:
        with open(states_save_path, "w+b") as states_file:
            pickle.dump(chat_states, states_file, pickle.HIGHEST_PROTOCOL)
            with open(users_save_path, "w+b") as users_file:
                pickle.dump(users_dict, users_file, pickle.HIGHEST_PROTOCOL)
            log.info("...success!")
    except Exception as exc:
        log.warning("can\'t save info: {}".format(exc))
    log.info("-=-=-= EXIT =-=-=-")


# noinspection PyUnusedLocal
def exit_handler(sig, frame):
    """
    Обработчик ``^C``.
    """
    save_chat_states()
    bot.stop_polling()
    for file in messages_log_files.values():
        if not file.closed:
            file.close()
    sys.exit(EXIT_SUCCESS)


def main() -> int:
    """
    Точка входа.

    :return: код выхода (сейчас не используется)
    :rtype: int
    """
    # Prepare home dir
    if not os.path.exists(root_path):
        os.makedirs(root_path)
    elif not os.path.isdir(root_path):
        os.remove(root_path)
        os.makedirs(root_path)

    # Prepare logger
    global log
    log = prepare_logger()

    log.info("-=-=-= NEW LAUNCH =-=-=-")

    # Prepare resources
    global soundboard_jojo_sounds
    for states_file in resource_listdir(config.JOJO, ""):
        if states_file.endswith(".mp3"):
            soundboard_jojo_sounds.append(states_file[:-4])  # strip '.mp3'

    global soundboard_gachi_sounds
    for states_file in resource_listdir(config.GACHI, ""):
        if states_file.endswith(".mp3"):
            soundboard_gachi_sounds.append(states_file[:-4])

    # Init VK API
    try:
        log.info("vk init...")
        vk_session = vk_api.VkApi(login=config.VK_LOGIN, password=config.VK_PASSWORD)
        vk_session.auth()
        global vk
        vk = vk_session.get_api()
        log.info("...success!")

        log.info("vk tools init...")
        global vk_tools
        vk_tools = VkTools(vk_session)
        log.info("...success!")

        log.info("vk test...")
        response = vk.groups.getById(group_id="team", fields="id", version=VK_VER)
        log.info("...success!")
        log.debug("With response: {}".format(response))
        global vk_disabled
        vk_disabled = False
    except Exception as exc:
        log.error("...failure! Reason: {}, VK disabled".format(exc))
        log.debug("With trace:\n{}".format(traceback.format_exc()))

    # Init whatanime.ga API
    try:
        log.info("whatanime init...")
        global whatanime
        whatanime = whatanime_ga.WhatAnimeClient(config.WHATANIME_TOKEN)
        log.info("...success! UID: {}".format(whatanime.user_id))
        global whatanime_disabled
        whatanime_disabled = False
    except Exception as exc:
        log.error("...failure! Reason: {}, whatanime disabled".format(exc))
        log.debug("With trace:\n{}".format(traceback.format_exc()))

    # Load info from disk
    states_save_path = os.path.join(root_path, "states.pkl")
    users_save_path = os.path.join(root_path, "users.pkl")
    log.info("loading info from {}...".format(root_path))
    try:
        with open(states_save_path, "rb") as states_file:
            global chat_states
            chat_states = pickle.load(states_file)
            with open(users_save_path, "rb") as users_file:
                global users_dict
                users_dict = pickle.load(users_file)
            log.info("...success!")
    except Exception as exc:
        log.warning("can\'t load info: {}".format(exc))
        log.debug("With trace:\n"
                  "{}".format(traceback.format_exc()))

    # Start
    log.info("Starting polling")
    bot.polling(none_stop=True)
    # Block thread!

    return EXIT_SUCCESS


if __name__ == '__main__':
    """
    Ловит и записывает любое исключение.
    """
    print("init!")
    signal.signal(signal.SIGINT, exit_handler)
    signal.signal(signal.SIGTERM, exit_handler)
    while True:
        # noinspection PyBroadException
        try:
            sys.exit(main())
        except Exception as e:
            e_str = "Unknown exception was raised!\n" \
                    "You can report issue w/ traceback at:\n" \
                    "https://github.com/saber-nyan/pod042-bot/issues\n" \
                    "(But do not report problems with Telegram server or network connection!)\n\n" \
                    "{}".format(traceback.format_exc())
            if log is None:
                log = prepare_logger()
            log.critical(e_str)
            save_chat_states()
            sys.exit(EXIT_UNKNOWN)
