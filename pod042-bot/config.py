# -*- coding: utf-8 -*-
"""
Файл конфигурации.
Также используется для поиска ресурсов.
"""
import os
import sys

# FROM ENV: SETTINGS! ###########################
# noinspection PyBroadException
from pathlib import Path

try:
    BOT_TOKEN = os.environ['BOT_TOKEN']  # Токен, полученный у @BotFather.
    BOT_USERNAME = os.environ['BOT_USERNAME']  # Username бота.
except:
    print('Please set needed env variables!\nRead more in config.py.', file=sys.stderr)
    sys.exit(-1)

# Из environmental variables:
# настройка = os.getenv('ключ', умолчание)

# Домашняя директория бота для логов и сохранений. Должны быть r/w права.
BOT_HOME = os.getenv('BOT_HOME', os.path.join(Path.home(), '.pod042-bot'))

VK_LOGIN = os.getenv('VK_LOGIN', None)  # Угу, ваш (или фейка) логин ВКонтакте. Лучше телефон.
VK_PASSWORD = os.getenv('VK_PASSWORD', None)  # Да, по другому никак. Проверено.
WHATANIME_TOKEN = os.getenv('WHATANIME_TOKEN', None)  # Токен whatanime.ga

# Кол-во постов для /vk_pic *на запрос*, не больше ста. Лимит = ITEMS_PER_REQUEST * 25
VK_ITEMS_PER_REQUEST = os.getenv('VK_ITEMS_PER_REQUEST', 11)
if VK_ITEMS_PER_REQUEST > 100:
    raise AttributeError("VK_ITEMS_PER_REQUEST is more than 100!\nRead more in config.py.")

NUM_THREADS = os.getenv('THREADS', 16)  # Кол-во потоков обработки запросов.

logfmt_default = '%(asctime)s (%(filename)s:%(lineno)d %(threadName)s) %(levelname)s - %(name)s: %(message)s'
LOG_FORMAT = os.getenv('LOG_FORMAT', logfmt_default)  # Формат лога. %%Зачем вам эта настройка?%%

# Уровни (даже не пытайтесь запихнуть число!):
# CRITICAL
# ERROR
# WARNING
# INFO
# DEBUG
# NOTSET
LOG_LEVEL = os.getenv('LOG_LEVEL', "INFO")  # Уровень лога.

# Логгировать в вывод? (Просто объявите переменную окружения 'LOG_TO_STDOUT_DISABLE')
LOG_TO_STDOUT = (False if 'LOG_TO_STDOUT_DISABLE' in os.environ else True)

# Логгировать в файл?
LOG_TO_FILE = (False if 'LOG_TO_FILE_DISABLE' in os.environ else True)

# Логгировать все сообщения. Логи не чистятся, через некоторое время будут весить по 1ГБ/файл!
LOG_INPUT = (True if 'LOG_INPUT' in os.environ else False)
#################################################
# BUILTIN: RESOURCES! ###########################
ROOT = 'pod042-bot.resources'

# # VIDEOS #####################
VIDEOS = ROOT + '.videos'
# ###
CODFISH = 'codfish.mp4'
# ##############################
# # AUDIOS #####################
# AUDIOS = ROOT + '.audios'
# # JOJO ######
# JOJO = AUDIOS + '.jojo'
# # GACHI #####
# GACHI = AUDIOS + '.gachi'
# #################################################
