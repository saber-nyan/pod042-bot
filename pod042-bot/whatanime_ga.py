# -*- coding: utf-8 -*-
"""
Модуль взаимодействия с https://whatanime.ga.
"""
import base64
import json
import os
import typing
from io import BytesIO
from urllib.parse import quote

import requests
from PIL import Image

try:
    from . import config
except ImportError:
    import config

ENDPOINT: str = "https://whatanime.ga"
tmp_path = os.path.join(config.BOT_HOME, "tmp")


class WhatAnimeResult:
    """
    Результат (одно аниме, а их несколько) поиска.
    """

    # ``from`` shadows Python builtin...
    # from: float = None
    # """
    # Starting time of the matching scene
    # """

    to: float = None
    """
    Ending time of the matching scene
    """

    at: float = None
    """
    Exact time of the matching scene
    """

    episode: int or str = None
    """
    The extracted episode number from filename
    """

    similarity: float = None
    """
    Similarity compared to the search image
    """

    anilist_id: int = None
    """
    The matching AniList ID
    """

    title: str = None
    """
    Japanese title
    """

    title_chinese: str = None
    """
    Chinese title
    """

    title_english: str = None
    """
    English title
    """

    title_romaji: str = None
    """
    Title in romaji
    """

    synonyms: typing.List[str] = None
    """
    Alternate english titles
    """

    synonyms_chinese: typing.List[str] = None
    """
    Alternate chinese titles
    """

    season: str = None
    """
    The parent folder where the file is located
    """

    anime: str = None
    """
    The folder where the file is located (This may act as a fallback when title is not found)
    """

    filename: str = None
    """
    The filename of file where the match is found
    """

    tokenthumb: str = None
    """
    A token for generating preview
    """

    thumb_path: str = None
    """
    Anime thumbnail path. ``None`` if ``load_thumbnail`` is not called.
    """

    preview_path: str = None
    """
    Anime video preview path. ``None`` if ``load_preview`` is not called.
    """

    request_params: typing.Dict[str, typing.Any] = None
    """
    Параметры для запроса миниатюры и превью.
    """

    def __str(self):
        return "{} EP#{}, similarity: {}".format(self.title_romaji, self.episode, self.similarity)

    def __str__(self):
        return self.__str()

    def __repr__(self):
        return self.__str()

    def __init__(self, response: json):
        self.__dict__.update(response)

        self.request_params = {
            "season": self.season,  # Опытным путем выяснил: они не обязательны.
            "anime": quote(self.anime, safe="~@#$&()*!+=:;,.?/\'"),  # Но тогда работает только с thumbnail.php
            "file": quote(self.filename, safe="~@#$&()*!+=:;,.?/\'"),
            "t": self.at,
            "token": self.tokenthumb,
        }

    def load_thumbnail(self):
        """
        Загружает миниатюру.
        """
        thumb_filename = os.path.join(tmp_path, "thumb_{}.jpg".format(self.filename))
        with open(thumb_filename, mode="wb") as file:
            response = requests.get("{}/thumbnail.php".format(ENDPOINT), params=self.request_params)
            file.write(response.content)
            self.thumb_path = os.path.realpath(file.name)

    def load_preview(self):
        """
        Загружает видео-превью.

        :except: при отсутствии превью
        """
        prev_filename = os.path.join(tmp_path, "prev_{}.mp4".format(self.filename))
        with open(prev_filename, mode="wb") as file:
            response = requests.get("{}/preview.php".format(ENDPOINT), params=self.request_params)
            file.write(response.content)
            self.preview_path = os.path.realpath(file.name)


class WhatAnimeClient:
    """
    Клиент для http://whatanime.ga.

    Документация: https://soruly.github.io/whatanime.ga
    """

    token: str = None
    """
    Токен.
    Для получения напишите soruly@gmail.com (или @soruly в Telegram).
    """

    user_id: int = None
    """
    UID пользователя.
    """

    email: str = None
    """
    e-mail пользователя.
    """

    quota: int = None
    """
    Квота: кол-во запросов за ``quota_ttl``.
    """

    quota_ttl: int = None
    """
    Сколько времени необходимо до обнуления ограничения квоты.
    В секундах.
    """

    now_quota: int = None
    """
    Количество оставшихся запросов.
    """

    quota_expire: int = None
    """
    Время до обнуления ``now_quota``.
    """

    def __init__(self, token: str):
        """
        :param str token: токен для доступа на сервер
        """
        self.token = token
        self.load_info(token)

    def load_info(self, token: str):
        """
        Загружает информацию о пользователе.

        :param str token: токен для доступа на сервер
        """
        response = requests.get("{}/api/me".format(ENDPOINT), params={
            "token": token,
        })
        self.__dict__.update(response.json())

    def search(self, picture_path: str) -> typing.List[WhatAnimeResult]:
        """
        Ищет аниме по скриншоту. Файлы, что в BASE64 > 1MB, не поддерживаются!

        :param picture_path: путь до картинки на диске
        :return: ответ сервера
        :rtype: WhatAnimeResult
        """
        with open(picture_path, mode="rb") as file:
            try:
                img: Image.Image = Image.open(file)
            except OSError as exc:
                raise IOError("file is not a picture") from exc
            out = BytesIO()
            img.save(out, "JPEG", quality=90)
        # Потратил 1.5 часа на отладку... оказалось, нужно просто написать "utf-8": к строке добавлялись b''
        # noinspection PyUnboundLocalVariable
        base64_encoded_image: str = str(base64.b64encode(out.getvalue()), "utf-8")
        response = requests.post("{}/api/search".format(ENDPOINT), params={
            "token": self.token,
        }, headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/64.0.3253.3 Safari/537.36",
        }, data={
            "image": "\'data:image/jpeg;base64," + base64_encoded_image + "\'",
        })
        resp_json = response.json()
        self.now_quota = resp_json["quota"]
        self.quota_expire = resp_json["expire"]
        results: typing.List[WhatAnimeResult] = []
        for item in resp_json["docs"]:
            results.append(WhatAnimeResult(item))
        return results
