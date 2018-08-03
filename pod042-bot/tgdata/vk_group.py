# -*- coding: utf-8 -*-
"""
Группа ВКонтакте для получения рандомного контента.
"""


class VkGroup:
    """
    Группа ВКонтакте.
    """
    vk_id: int
    name: str
    url_name: str

    def __init__(self, vk_id: int, name: str, url_name: str):
        """
        :param int vk_id: ID группы на сервере
        :param str name: Human-readable название группы
        :param str url_name: Название группы для URL
        """
        self.vk_id = vk_id
        self.name = name
        self.url_name = url_name

    def __str(self) -> str:
        return "{} ({}) #{}".format(self.name, self.url_name, self.vk_id)

    def __str__(self) -> str:
        return self.__str()

    def __repr__(self) -> str:
        return self.__str()
