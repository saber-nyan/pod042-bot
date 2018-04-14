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
import string
import sys
import time
import traceback
import typing
from datetime import datetime

import pkg_resources
import requests
import telebot
from telebot import util
from telebot.types import Message, User, Chat, PhotoSize, File, Document, \
    ForceReply, InlineQuery, InlineQueryResultVoice
from vk_api import vk_api, VkTools
from vk_api.vk_api import VkApiMethod

try:
    from . import config
    from .tgdata import vk_group, chat_state
    from .external_api import whatanime_ga
    from .external_api import iqdb_org
    from .tgdata.inline_sound import InlineSound
except ImportError:
    from tgdata import chat_state, vk_group
    from tgdata.inline_sound import InlineSound
    from external_api import whatanime_ga, iqdb_org
    import config

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

soundboard_sounds: typing.List[InlineSound] = []
"""
Список звуков soundboard для inline-бота.
"""

inline_disabled = True

messages_log_files: typing.Dict[int, io.StringIO] = {}
"""
Словарь файлов для полного логгирования чатов.
msg.chat.id <-> file stream (io.StringIO)
"""

log: logging.Logger = None

logs_path = os.path.join(config.BOT_HOME, "logs")
saves_path = os.path.join(config.BOT_HOME, "saves")
tmp_path = os.path.join(config.BOT_HOME, "tmp")

bot = telebot.TeleBot(config.BOT_TOKEN, num_threads=config.NUM_THREADS)
iqdb: iqdb_org.IqdbClient = None
iqdb_disabled = True
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

# status emoji
ready = "\u2705 "
pending = "\u2747\ufe0f "
not_ready = "\u274e "
error = "\u203c\ufe0f "


def download_and_report_progress(msg: Message, max_file_size: int
                                 ) -> typing.Optional[typing.Tuple[str, Message]]:
    """
    Загружает файл и сообщает об этом в указанном чате.

    :param Message msg: сообщение-источник
    :param int max_file_size: максимальный размер для загрузки
    :return: путь до скачанного файла И
    :rtype: typing.Optional[typing.Tuple[str, Message]]
    """
    chat_id = msg.chat.id
    msg_text = msg.text

    if (msg.photo is None and msg.document is None) and not msg_text.startswith(("http://", "https://",)):
        log.debug(f"not link, skipping: {msg.text}")
        return None

    # Prepare URL
    status_msg = bot.send_message(chat_id, pending + "Подготовка ссылки\n" +
                                  not_ready + "Загрузка\n" +
                                  not_ready + "Поиск\n" +
                                  not_ready + "Результат\n" +
                                  not_ready + "Превью\n")
    if msg.photo is not None:  # Фото, .jpg
        photos: typing.List[PhotoSize] = msg.photo
        file: File = bot.get_file(photos[-1].file_id)  # Biggest resolution
        download_url = f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{file.file_path}"
        log.debug("pic")
    elif msg.document is not None:  # Документ, any!
        document: Document = msg.document
        file: File = bot.get_file(document.file_id)
        download_url = f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{file.file_path}"
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
        return None
    log.debug(f"ready to download input, url: {download_url}")

    # Download!
    try:
        status_msg = bot.edit_message_text(ready + "Подготовка ссылки\n" +
                                           pending + "Загрузка\n" +
                                           not_ready + "Поиск\n" +
                                           not_ready + "Результат\n" +
                                           not_ready + "Превью\n",
                                           chat_id, status_msg.message_id)
        response = requests.get(download_url, timeout=4, stream=True)
        data = response.raw.read(max_file_size + 1, decode_content=True)
        if len(data) > max_file_size:  # 2MB
            response.close()
            bot.edit_message_text(ready + "Подготовка ссылки\n" +
                                  error + "Загрузка\n" +
                                  not_ready + "Поиск\n" +
                                  not_ready + "Результат\n" +
                                  not_ready + "Превью\n",
                                  chat_id, status_msg.message_id)
            bot.send_message(chat_id, "Объем данных превышает 2МБ, отменено. Жду еще одного сообщения или /abort!")
            return None
        # noinspection PyUnusedLocal
        rand = "".join(random.choice(string.ascii_letters + string.digits) for x in range(
            random.randint(16, 32)))
        search_file_path = os.path.join(tmp_path, f"search_{msg.message_id}_{rand}")
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
        # log.debug("{}".format(traceback.format_exc()))
        log.info("dload fail:", exc_info=True)
        # noinspection PyBroadException
        try:
            # noinspection PyUnboundLocalVariable
            os.remove(os.path.realpath(search_file_path))
        except:
            pass
        return None

    status_msg = bot.edit_message_text(ready + "Подготовка ссылки\n" +
                                       ready + "Загрузка\n" +
                                       pending + "Поиск\n" +
                                       not_ready + "Результат\n" +
                                       not_ready + "Превью\n",
                                       chat_id, status_msg.message_id)
    return search_file_path, status_msg


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


def is_admin(chat_msg: Message) -> bool:
    """
    Проверяет, отправлено ли сообщение администратором бота.

    :param Message chat_msg: сообщение из чата
    :return: ``True``, если отправитель является администратором
    :rtype: bool
    """
    if config.ADMIN_USERNAME is None:
        return False
    sender: User = chat_msg.from_user
    log.debug(f"{sender.username} admin check...")
    return True if sender.username == config.ADMIN_USERNAME else False


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


# noinspection PyBroadException
@bot.message_handler(commands=["eval", ], func=is_admin)
def bot_cmd_eval(msg: Message):
    """
    Позволяет запустить любой кусок Python кода на сервере.
    Доступно только администратору.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    if len(msg.text.split()) <= 1:
        bot.send_message(chat_id, "Укажите строчку кода после команды!")
        return
    cmd: str = msg.text.split(' ', 1)[1]
    try:
        cmd = "cmd_result = " + cmd
        log.debug(f"compiling {cmd}...")
        cmd_compiled = compile(cmd, "<string>", "exec")
        exec(cmd_compiled, globals(), locals())
        result = locals().get("cmd_result")
    except Exception as exc:
        result = f"Exception: {exc}\n{traceback.format_exc()}"
    for splitted in util.split_string(str(result), 2000):
        bot.send_message(chat_id, splitted)


@bot.message_handler(commands=["list_chats", ], func=is_admin)
def bot_cmd_list_chats(msg: Message):
    """
    Возвращает список чатов и их состояние.
    Доступно только администратору.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    result = ""
    for other_chat_id, other_chat_state in chat_states.items():
        if hasattr(other_chat_state, "title"):  # TODO: remove compatibility condition?
            result += f"<code>{other_chat_id}</code>: {other_chat_state.title}, " \
                      f"state <code>{other_chat_state.state_name}</code>\n"
        else:
            result += f"<code>{other_chat_id}</code>: state <code>{other_chat_state.state_name}</code>\n"
    bot.send_message(chat_id, result, parse_mode="HTML")


@bot.message_handler(commands=["send_msg", ], func=is_admin)
def bot_cmd_send_msg(msg: Message):
    """
    Отправляет собщение на указанный ``chat_id``.
    Доступно только администратору.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    in_text = msg.text
    if len(in_text.split()) < 3:
        bot.send_message(chat_id, "Команда работает в следующем формате:\n"
                                  "<code>/send_msg chat_id msg</code>", parse_mode="HTML")
        return
    _, out_chat_id, out_text = in_text.split(' ', 2)
    try:
        bot.send_message(int(out_chat_id), out_text, parse_mode="HTML")
        bot.send_message(chat_id, "Выполнено.")
    except Exception as exc:
        bot.send_message(chat_id, "Exception: {}\n{}".format(exc, traceback.format_exc()))


@bot.message_handler(commands=["info", ])
def bot_cmd_info(msg: Message):
    """
    Информация о боте и чате.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    # TODO


# noinspection PyBroadException
@bot.message_handler(func=lambda msg: chat_in_state(msg, chat_state.IQDB),
                     content_types=["text", "document", "photo"])
def bot_process_iqdb(msg: Message):
    """
    Ищет арт на бурах с помощью `iqdb.org`.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id

    try:
        search_file_path, status_msg = download_and_report_progress(msg, iqdb_org.MAX_SIZE)
    except TypeError:
        return

    try:
        results: typing.List[iqdb_org.IqdbResult] = iqdb.search(search_file_path)
        result = results[0]
        bot.edit_message_text(ready + "Подготовка ссылки\n" +
                              ready + "Загрузка\n" +
                              ready + "Поиск\n" +
                              ready + "Результат\n" +
                              ready + "Превью\n",
                              chat_id, status_msg.message_id)
        out_msg = f"{result.match_type} ({result.similarity}%): {result.rating}, {result.resolution}\n" \
                  f"Preview: {result.preview_link}\n" \
                  f"Sauce: {result.source_link}"
        if result.tags is not None:
            out_msg += "\n\nTags: "
            for tag in result.tags:
                out_msg += f"<code>{tag}</code> "
        bot.send_message(chat_id, out_msg, parse_mode="HTML")
        chat_states[chat_id].state_name = chat_state.NONE
    except Exception as exc:
        bot.edit_message_text(ready + "Подготовка ссылки\n" +
                              ready + "Загрузка\n" +
                              error + "Поиск\n" +
                              not_ready + "Результат\n" +
                              not_ready + "Превью\n",
                              chat_id, status_msg.message_id)
        bot.send_message(chat_id, f"Ошибка при поиске. Жду еще одного сообщения или /abort!\n"
                                  f"Подробнее: {exc}")
        log.info("search fail:", exc_info=True)

    # noinspection PyBroadException
    try:
        os.remove(os.path.realpath(search_file_path))
    except:
        pass


@bot.message_handler(func=lambda msg: chat_in_state(msg, chat_state.WHATANIME),
                     content_types=["text", "document", "photo"])
def bot_process_whatanime(msg: Message):
    """
    Ищет скриншот из аниме с помощью `whatanime.ga`.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id

    try:
        search_file_path, status_msg = download_and_report_progress(msg, 2097152)
    except TypeError:
        return

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
        bot.send_message(chat_id, f"<code>{result.title_romaji}</code>", parse_mode="HTML")
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
        log.info("search fail:", exc_info=True)
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
        log.debug("preview fail:", exc_info=True)

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
            log.debug(f"line {line}")
            if not VK_GROUP_REGEX.match(line):
                dead_links.append(line)
                break
            group_name: str = re.sub(VK_GROUP_REGEX, r"\1", line)
            log.debug(f"got group \"{group_name}\"...")
            try:
                response = vk.groups.getById(group_id=group_name, fields="id", version=VK_VER)
            except (vk_api.ApiError, vk_api.ApiHttpError) as err:
                log.info(f"...but request failed ({err})")
                dead_links.append(line)
                break
            log.debug(f"...and vk response:\n"
                      f"{response}")
            group_dict: dict = response[0]
            group = vk_group.VkGroup(group_dict["id"], group_dict["name"], group_dict["screen_name"])
            log.info(f"finally, our group: {group}")
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

    out_msg = f"Вошел в режим <b>Конфигурация модуля ВКонтакте</b>!\n" \
              f"/add — добавление групп\n" \
              f"/clear — очистка списка\n" \
              f"/abort — отмена\n\n" \
              f"Сейчас в списке:\n" \
              f"<code>{grps_str}</code>\n"
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
    log.debug(f"selected {chosen_group} as source")
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
                log.debug(f"attach {photo_attach}")
                max_size = 75
                for key in photo_attach:  # Аццкий костыль для выбора фото максимального разрешения
                    value = photo_attach[key]
                    log.debug(f"<{key}> -> {value}")
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

    bot.send_message(chat_id, f"{max_size_url}\n"
                              f"Из https://vk.com/{chosen_group.url_name}")


@bot.message_handler(commands=["whatanime", ])
def bot_cmd_whatanime(msg: Message):
    """
    Входит в режим поиска аниме по скриншоту (спасибо whatanime.ga за API).

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    if whatanime_disabled:
        bot.send_message(chat_id, "Модуль whatanime.ga отключен.")
        return
    chat_states[chat_id].state_name = chat_state.WHATANIME
    out_msg = "Вошел в режим <b>whatanime.ga: поиск аниме</b>!\n" \
              "Напиши /abort для выхода.\n\n" \
              "Для поиска отправь картинку или <b>прямую</b> ссылку (должна начинаться с http/https)."
    bot.send_message(chat_id, out_msg, parse_mode="HTML")


@bot.message_handler(commands=["iqdb", ])
def bot_cmd_iqdb(msg: Message):
    """
    Входит в режим поиска соуса арта (не спасибо iqdb.org за отсутствие API).

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    chat_id = msg.chat.id
    if iqdb_disabled:
        bot.send_message(chat_id, "Модуль iqdb.org отключен.")
        return
    chat_states[chat_id].state_name = chat_state.IQDB
    out_msg = "Вошел в режим <b>iqdb.org: multi-service image search</b>!\n" \
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
    codfish_video = pkg_resources.resource_stream(config.VIDEOS, config.CODFISH)  # Our codfish video
    if len(words) <= 1:  # No username
        bot.send_message(chat_id, "Укажи юзернейм кого бить!")
    elif username == bot.get_me().username:  # Himself
        bot.send_video(chat_id, codfish_video, caption="Хорошенько шлепнул себя треской.")
    elif username in users_dict:  # Search in our users dict (user_id's are unique?)
        # raw = requests.get("https://api.telegram.org:443/bot{}/getChatMember?chat_id={}&user_id={}"
        #                    .format(config.BOT_TOKEN, chat_id, users_dict[username]))  # Get user first name
        # response_json: tuple = raw.json()
        # # noinspection PyTypeChecker
        # user_first_name = response_json["result"]["user"]["first_name"]
        user_first_name = bot.get_chat_member(chat_id, users_dict[username]).user.first_name
        log.debug(f"user first name is {user_first_name}")
        bot.send_video(chat_id, codfish_video, caption=f"Хорошенько шлепнул {user_first_name} треской.")
    else:  # Unknown
        bot.send_message(chat_id, f"Извини, пока не знаю <b>{username}</b>...", parse_mode="HTML")


@bot.message_handler(commands=["quote", ])
def bot_cmd_quote(msg: Message):
    """
    Посылает рандомную цитату с `tproger.ru`.

    :param Message msg: сообщение
    """
    bot_all_messages(msg)
    quote = requests.get("https://tproger.ru/wp-content/plugins/citation-widget/getQuotes.php").text
    bot.send_message(msg.chat.id, f"<code>{quote}</code>", parse_mode="HTML")


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
    bot.send_message(msg.chat.id, f"<code>{out_msg}</code>", parse_mode="HTML")


@bot.inline_handler(lambda a: True)
def bot_inline_handler(inline_query: InlineQuery):
    """
    Отвечает на inline списокм звуков, полученных с указанного в config сервера.

    :param InlineQuery inline_query: inline запрос
    """
    if inline_disabled:
        log.info("tried inline, disabled")
        return
    log.debug(f"got inline {inline_query.query}")

    results = []
    id_counter = 0
    for sound in soundboard_sounds:
        if sound.pretty_name.find(inline_query.query) != -1 or sound.category.find(inline_query.query) != -1:
            if id_counter > 20:
                break  # Display only 20
            id_counter += 1
            results.append(InlineQueryResultVoice(id_counter, config.SERVER_ADDRESS + sound.full_url,
                                                  title=sound.pretty_name, performer=sound.category))
    bot.answer_inline_query(inline_query.id, results)


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
    chat_title = chat.title if chat.title is not None else chat.username
    if chat_id not in chat_states:
        log.debug("chat not known")
        chat_states[chat_id] = chat_state.ChatState(chat_state.NONE, chat_title)
    else:
        log.debug("chat known")
        if not hasattr(chat_states[chat_id], "title"):
            chat_states[chat_id].title = chat_title
    if config.LOG_INPUT:
        global messages_log_files
        if chat_id not in messages_log_files:
            def tidy_str(old_str):
                """
                Оставляет только безопасные символы.
                """
                new_str = ""
                for char in old_str:
                    if char in (string.ascii_letters + string.digits + ' '):
                        new_str += char
                return new_str
            base_name = "chat_{}.log".format(tidy_str(chat_title))
            log_path = os.path.join(logs_path, base_name)
            messages_log_files[chat_id] \
                = open(log_path, mode="at", buffering=1, encoding="utf-8", errors="backslashreplace")
            messages_log_files[chat_id].write("with id: {}\n".format(chat_id))
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
        fh = logging.FileHandler(os.path.join(logs_path, "main.log"))
        fh.setFormatter(formatter)
        fh.setLevel(loglevel)
        l_log.addHandler(fh)
        l_log.info("Logs path: {}".format(os.path.join(logs_path, "main.log")))
    return l_log


# noinspection PyBroadException
def save_chat_states():
    """
    Сохряняет состояние чатов и пользователей в ``.pkl``-файл.
    """
    states_save_path = os.path.join(saves_path, "states.pkl")
    users_save_path = os.path.join(saves_path, "users.pkl")
    global log
    if log is None:
        log = prepare_logger()
    retry_count = 1
    while retry_count < 6:
        log.info(f"saving info to {saves_path} (try #{retry_count})...")
        try:
            with open(states_save_path, "w+b") as states_file:
                pickle.dump(chat_states, states_file, pickle.HIGHEST_PROTOCOL)
                with open(users_save_path, "w+b") as users_file:
                    pickle.dump(users_dict, users_file, pickle.HIGHEST_PROTOCOL)
                log.info("...success!")
                break
        except:
            log.error(f"(try #{retry_count}) SHIT! Save failed!", exc_info=True)
            time.sleep(retry_count)  # Not a bug, lol
            retry_count += 1


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
    log.info("-=-=-= EXIT =-=-=-")
    sys.exit(EXIT_SUCCESS)


# noinspection PyBroadException
def main() -> int:
    """
    Точка входа.

    :return: код выхода (сейчас не используется)
    :rtype: int
    """
    # Prepare home dir
    if not os.path.exists(config.BOT_HOME):
        os.makedirs(config.BOT_HOME)
        os.makedirs(logs_path)
        os.makedirs(saves_path)
        os.makedirs(tmp_path)
    elif not os.path.isdir(config.BOT_HOME):
        os.remove(config.BOT_HOME)
        os.makedirs(config.BOT_HOME)
        os.makedirs(logs_path)
        os.makedirs(saves_path)
        os.makedirs(tmp_path)

    # Prepare logger
    global log
    log = prepare_logger()

    log.info("-=-=-= NEW LAUNCH =-=-=-")

    # Init inline queries
    try:
        log.info("inline init...")
        global soundboard_sounds
        response = requests.get(config.SERVER_ADDRESS + "/index.json")
        json_arr = response.json()
        for sound in json_arr:
            soundboard_sounds.append(InlineSound(sound))
        global inline_disabled
        inline_disabled = False
        log.info("...success!")
    except:
        log.error("...failure, inline disabled!", exc_info=True)

    # Init VK API
    try:
        log.info("vk init...")
        vk_session = vk_api.VkApi(login=config.VK_LOGIN, password=config.VK_PASSWORD,
                                  config_filename=os.path.join(saves_path, 'vk_config.v2.json'),
                                  api_version=str(VK_VER))
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
    except:
        log.error("...failure, VK disabled!", exc_info=True)

    # Init whatanime.ga API
    try:
        log.info("whatanime init...")
        global whatanime
        whatanime = whatanime_ga.WhatAnimeClient(config.WHATANIME_TOKEN)
        log.info("...success! UID: {}".format(whatanime.user_id))
        global whatanime_disabled
        whatanime_disabled = False
    except:
        log.error("...failure, whatanime disabled!", exc_info=True)

    # Init iqdb.org API
    try:
        log.info("iqdb init...")
        global iqdb
        iqdb = iqdb_org.IqdbClient()
        log.info("...success! Boorus:\n{}".format(iqdb.boorus_status))
        global iqdb_disabled
        iqdb_disabled = False
    except:
        log.error("...failure, iqdb disabled!", exc_info=True)

    # Load info from disk
    states_save_path = os.path.join(saves_path, "states.pkl")
    users_save_path = os.path.join(saves_path, "users.pkl")
    retry_count = 1
    while retry_count < 6:
        log.info(f"loading info from {saves_path} (try #{retry_count})...")
        try:
            with open(states_save_path, "rb") as states_file:
                global chat_states
                chat_states = pickle.load(states_file)
                with open(users_save_path, "rb") as users_file:
                    global users_dict
                    users_dict = pickle.load(users_file)
                log.info("...success!")
                break
        except:
            log.error(f"(try #{retry_count}) SHIT! Load failed!", exc_info=True)
            time.sleep(retry_count)  # Not a bug too
            retry_count += 1

    telebot.logger.setLevel(config.LOG_LEVEL)
    telebot.apihelper.proxy = {
        'http': config.PROXY,
        'https': config.PROXY,
    }

    # Start
    log.info("Starting polling")
    bot.polling(none_stop=True)
    # Block thread!

    log.info("Stopped!")

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
            log.info("Stopped!")
            sys.exit(EXIT_UNKNOWN)
