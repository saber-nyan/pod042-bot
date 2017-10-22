# -*- coding: utf-8 -*-
"""
Файл конфигурации.
Также используется для поиска ресурсов.
"""
import logging
import os
import sys

# FROM ENV: SETTINGS! ###########################
# noinspection PyBroadException
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']  # Токен, полученный у @BotFather.
    BOT_USERNAME = os.environ['BOT_USERNAME']  # Username бота.
except:
    print('Please set BOT_TOKEN and BOT_USERNAME env variables!\nRead more in config.py.', file=sys.stderr)
    sys.exit(-1)

NUM_THREADS = os.getenv('BOT_THREADS', 16)  # Кол-во потоков обработки запросов.

logfmt_default = '%(asctime)s (%(filename)s:%(lineno)d %(threadName)s) %(levelname)s - %(name)s: %(message)s'
LOG_FORMAT = os.getenv('BOT_LOG_FORMAT', logfmt_default)  # Формат лога.
LOG_LEVEL = logging.INFO  # Уровень лога.

# Логгировать в вывод? (Просто объявите переменную окружения)
LOG_TO_STDOUT = (False if 'LOG_TO_STDOUT_DISABLE' in os.environ else True)

# Логгировать в файл?
LOG_TO_FILE = (False if 'LOG_TO_FILE_DISABLE' in os.environ else True)
#################################################
# BUILTIN: RESOURCES! ###########################
ROOT = 'pod042-bot.resources'

# VIDEOS #####################
VIDEOS = ROOT + '.videos'
###
CODFISH = 'codfish.mp4'
##############################
# AUDIOS #####################
AUDIOS = ROOT + '.audios'
# JOJO ######
JOJO = AUDIOS + '.jojo'
# GACHI #####
GACHI = AUDIOS + '.gachi'
#################################################
