# -*- coding: utf-8 -*-
"""
Используется в сложных коммандах, состоящих
из нескольких шагов.
"""

NONE = ""
SOUNDBOARD_JOJO = "JoJo's Bizarre Adventure soundboard"
SOUNDBOARD_GACHI = "Gachimuchi soundboard"
CONFIGURE_VK_GROUPS = "Конфигурация модуля ВКонтакте"
CONFIGURE_VK_GROUPS_ADD = "Добавление групп ВК для постинга картинок"


class ChatState:
    """
    Состояние бота в одной из комнат.
    """

    """
    Название запущенного запроса.
    Если строка пуста -- запрос не запущен. 
    Для отмены используется ``/abort``.
    """
    started_request_name: str = NONE

    """
    ID сообщения, на которое необходим ответить для добавления групп ВК.
    """
    message_id_to_reply = None

    def __init__(self, started_request_name, message_id_to_reply=None):
        """
        :param started_request_name: Название запущенного запроса. Если строка пуста -- запрос не запущен.
        :param message_id_to_reply: ID сообщения, на которое необходим ответить для добавления групп ВК.
        """
        self.started_request_name = started_request_name
        self.message_id_to_reply = message_id_to_reply
