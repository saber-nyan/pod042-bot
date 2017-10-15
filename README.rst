pod042-bot
##########

Бесполезный Telegram-бот. Для меня, тебя и того парня в пакете. Подтверждена работа под M$® Windows™!

Имеет смысл использовать в групповых чатах.

.. image:: https://i.imgur.com/ORL9f5E.png

*********
Установка
*********
.. code-block:: bash

    $ git clone https://github.com/saber-nyan/pod042-bot.git && cd pod042-bot

Затем в директории pod042-bot необходимо создать файл ``config.py`` с таким содержанием:

.. code-block:: python

    # -*- coding: utf-8 -*-
    import logging

    BOT_TOKEN = "123456789:qncAdkfKcDkkfOdamdfsnKAbksbdlfVnxn"  # Токен, полученный у @BotFather. И не надейтесь, сюда я ввел случайный.
    BOT_USERNAME = "my_bot"  # Username бота.

    NUM_THREADS = 16  # Кол-во потоков обработки запросов.

    LOG_FORMAT = '%(asctime)s (%(filename)s:%(lineno)d %(threadName)s) %(levelname)s - %(name)s: "%(message)s"'  # Формат лога.
    LOG_LEVEL = logging.INFO  # Уровень лога.

После этого, в корневой директории репозитория:

.. code-block:: bash

    # Рекомендую завести virtualenv:
    $ virtualenv ./venv
    $ source ./venv/bin/activate
    ##############################
    $ python3 ./setup.py install
    
    $ cd
    $ python3 -m pod042-bot