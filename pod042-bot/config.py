# -*- coding: utf-8 -*-
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

LOG_TO_STDOUT = True
if 'LOG_TO_STDOUT_DISABLE' in os.environ:  # Логгировать в вывод? (Просто объявите переменную окружения)
    LOG_TO_STDOUT = False

LOG_TO_FILE = True
if 'LOG_TO_FILE_DISABLE' in os.environ:  # Логгировать в файл?
    LOG_TO_FILE = False

#################################################
# BUILTIN: RESOURCES! ###########################
ROOT = 'pod042-bot.resources'

# VIDEOS #####################
VIDEOS = ROOT + '.videos'
###
CODFISH = 'codfish.webm'
##############################
#################################################
