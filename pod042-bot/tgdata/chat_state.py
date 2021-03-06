# -*- coding: utf-8 -*-
"""
Используется в сложных коммандах, состоящих
из нескольких шагов.
"""
import typing

try:
    from .vk_group import VkGroup
except ImportError:
    from tgdata.vk_group import VkGroup

NONE = "Нет"
WHATANIME = "whatanime.ga: поиск аниме"
IQDB = "iqdb.org: multi-service image search"
CONFIGURE_VK_GROUPS = "Конфигурация модуля ВКонтакте"
CONFIGURE_VK_GROUPS_ADD = "Добавление групп ВК для постинга картинок"


class ChatState:
    """
    Состояние бота в одной из комнат.
    """

    state_name: str
    """
    Название запущенного запроса.
    Для отмены используется ``/abort``.
    """

    message_id_to_reply: int
    """
    ID сообщения, на которое необходим ответить для действия.
    """

    vk_groups: typing.List[VkGroup]
    """
    Список групп, откуда берется контент.
    group_name <-> VkGroup
    """

    title: str
    """
    Название чата.
    """

    member_usernames: typing.List[str]
    """
    Список юзернеймов членов текущего чата: в Telegram нет API для получения
    таких данных!
    """

    def __init__(self, state_name: str, title: str, message_id_to_reply=None, vk_groups=None, member_usernames=None):
        """
        :param str state_name: Название запущенного запроса. Если строка пуста -- запрос не запущен.
        :param str title: Название чата.
        :param message_id_to_reply: ID сообщения, на которое необходим ответить для действия.
        :param typing.List[VkGroup] vk_groups: Список групп, откуда берется контент.
        :param typing.List[str] member_usernames: Список юзернеймов членов текущего чата.
        """
        if member_usernames is None:
            member_usernames = []
        if vk_groups is None:
            vk_groups = [VkGroup(29937425, "Sailor fuku", "seifuku_blog"), ]
        self.state_name = state_name
        self.title = title
        self.message_id_to_reply = message_id_to_reply
        self.vk_groups = vk_groups
        self.member_usernames = member_usernames

    def __str(self) -> str:
        return f"{self.title}, members: {self.member_usernames}"

    def __str__(self) -> str:
        return self.__str()

    def __repr__(self) -> str:
        return self.__str()




