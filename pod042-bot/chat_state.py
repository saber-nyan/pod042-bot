# -*- coding: utf-8 -*-
"""
Используется в сложных коммандах, состоящих
из нескольких шагов.
"""
import typing

try:
    from .vk_group import VkGroup
except ImportError:
    from vk_group import VkGroup

NONE = "Нет"
WHATANIME = "whatanime.ga: поиск аниме"
SOUNDBOARD_JOJO = "JoJo's Bizarre Adventure soundboard"
SOUNDBOARD_GACHI = "Gachimuchi soundboard"
CONFIGURE_VK_GROUPS = "Конфигурация модуля ВКонтакте"
CONFIGURE_VK_GROUPS_ADD = "Добавление групп ВК для постинга картинок"


class ChatState:
    """
    Состояние бота в одной из комнат.
    """

    state_name: str = NONE
    """
    Название запущенного запроса.
    Для отмены используется ``/abort``.
    """

    message_id_to_reply = None
    """
    ID сообщения, на которое необходим ответить для действия.
    """

    vk_groups: typing.List[VkGroup] = [VkGroup(29937425, "Sailor fuku", "seifuku_blog"), ]  # 10/10 азиаточки
    """
    Список групп, откуда берется контент.
    group_name <-> VkGroup
    """

    def __init__(self, state_name: str, message_id_to_reply=None, vk_groups=None):
        """
        :param str state_name: Название запущенного запроса. Если строка пуста -- запрос не запущен.
        :param message_id_to_reply: ID сообщения, на которое необходим ответить для действия.
        :param typing.List[VkGroup] vk_groups: Список групп, откуда берется контент.
        """
        if vk_groups is None:
            vk_groups = [VkGroup(29937425, "Sailor fuku", "seifuku_blog"), ]
        self.state_name = state_name
        self.message_id_to_reply = message_id_to_reply
        self.vk_groups = vk_groups
