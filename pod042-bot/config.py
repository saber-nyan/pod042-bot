# -*- coding: utf-8 -*-
"""
Файл конфигурации.
Также используется для поиска ресурсов.
"""
import os
import sys
from pathlib import Path


# FROM ENV: SETTINGS! ###########################
# noinspection PyBroadException
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']  # Токен, полученный у @BotFather.
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
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', None)  # Юзернейм админа. Ему будут доступны команды управления ботом.

# Прокси в формате `socks5://user:pass@host:port`
PROXY = os.getenv('PROXY', None)

# Адрес сервера, откуда берутся звуки для inline.
# Сервер должен быть доступен извне!
# В корне сервера должен лежать index.json c таким содержанием:
# [
#   {
#     "pretty_name": "then you and i should uhh settle it then",
#     "category": "gachi",
#     "full_url": "/soundboard/gachi/then_you_and_i_should_uhh_settle_it_then.mp3"
#   },
#   {
#     "pretty_name": "huh1",
#     "category": "gachi",
#     "full_url": "/soundboard/gachi/huh1.mp3"
#   }
# ]
# где:
# pretty_name : имя для отображения в списке
# category    : категория звука (добавляется к имени для удобного выбора)
# full_url    : путь к файлу на сервере
#
# В формате `http://saber-nyan.test.ga`, ОЧЕНЬ ВАЖНО НЕ ИСПОЛЬЗОВАТЬ IP-АДРЕС, РАБОТАЕТ ЛИШЬ С ХОСТНЕЙМОМ
SERVER_ADDRESS = os.getenv('SERVER_ADDRESS', None)

# Кол-во постов для /vk_pic *на запрос*, не больше ста. Лимит = ITEMS_PER_REQUEST * 25
VK_ITEMS_PER_REQUEST = os.getenv('VK_ITEMS_PER_REQUEST', 11)
if VK_ITEMS_PER_REQUEST > 100:
    raise AttributeError("VK_ITEMS_PER_REQUEST is more than 100!\nRead more in config.py.")

NUM_THREADS = os.getenv('THREADS', 16)  # Кол-во потоков обработки запросов.

# neuroshit #######

# Необходимо скопировать переменные, полученные после установки torch7 в ваш env-файл!
# У меня это:
'''
LUA_PATH='/home/saber-nyan/.luarocks/share/lua/5.1/?.lua;/home/saber-nyan/.luarocks/share/lua/5.1/?/init.lua;/home/saber-nyan/torch/install/share/lua/5.1/?.lua;/home/saber-nyan/torch/install/share/lua/5.1/?/init.lua;./?.lua;/home/saber-nyan/torch/install/share/luajit-2.1.0-beta1/?.lua;/usr/local/share/lua/5.1/?.lua;/usr/local/share/lua/5.1/?/init.lua'
LUA_CPATH='/home/saber-nyan/.luarocks/lib/lua/5.1/?.so;/home/saber-nyan/torch/install/lib/lua/5.1/?.so;./?.so;/usr/local/lib/lua/5.1/?.so;/usr/local/lib/lua/5.1/loadall.so'
PATH=/home/saber-nyan/torch/install/bin:$PATH
LD_LIBRARY_PATH=/home/saber-nyan/torch/install/lib:$LD_LIBRARY_PATH
DYLD_LIBRARY_PATH=/home/saber-nyan/torch/install/lib:$DYLD_LIBRARY_PATH
LUA_CPATH='/home/saber-nyan/torch/install/lib/?.so;'$LUA_CPATH
'''

# Директория с установкой torch-rnn. И нет, я пробовал докер, мне так удобнее.
# /home/saber-nyan/Documents/WORKDIR/ML/torch-rnn/
NEURO_WORKDIR = os.getenv('NEURO_WORKDIR', None)

# Путь до модели.
# /home/saber-nyan/Documents/WORKDIR/ML/models/3L_256_b_s_pr_a_po_ja_d_soc_222500.t7
NEURO_MODEL_PATH = os.getenv('NEURO_MODEL_PATH', None)

# Номер GPU для CUDA/OpenCL; -1 для работы на CPU. Не сильно медленнее, кстати.
NEURO_GPU = os.getenv('NEURO_GPU', -1)

# Температора для нейронной сети. Чем больше температура, тем меньше она исходит из текста модели.
NEURO_TEMP = os.getenv('NEURO_TEMP', 0.4)
###################
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

# VIDEOS #####################
VIDEOS = ROOT + '.videos'
###
CODFISH = 'codfish.mp4'

#################################################
