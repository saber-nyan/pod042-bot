# -*- coding: utf-8 -*-
"""
Используется в сложных коммандах, состоящих
из нескольких шагов.
"""

SOUNDBOARD_JOJO = "JoJo's Bizarre Adventure soundboard"
SOUNDBOARD_GACHI = "Gachimuchi soundboard"


class ChatState:
    """
    Состояние бота в одной из комнат.
    """

    """
    Название запущенного запроса.
    Если строка пуста -- запрос не запущен. 
    Для отмены используется ``/abort``.
    """
    started_request_name: str = ""

    def __init__(self, started_request_name):
        self.started_request_name = started_request_name
