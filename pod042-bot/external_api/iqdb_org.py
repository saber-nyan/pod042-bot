# -*- coding: utf-8 -*-
"""
Модуль взаимодействия с https://iqdb.org
"""
import re
from enum import Enum
from io import BytesIO
from typing import List, Optional

import requests
from PIL import Image
# noinspection PyProtectedMember
from bs4 import BeautifulSoup, Tag

FAIL_COUNT_REGEX = re.compile(r".*?(\d+).*")
FAIL_REASON_REGEX = re.compile(r".*Last reason: (.*)\)", re.DOTALL)

ENDPOINT: str = "https://iqdb.org"
MAX_SIDE_RESOLUTION: int = 7500
MAX_SIZE: int = 8388608  # in bytes
# SUPPORTED_FORMATS: List = ["PNG", "JPEG", "GIF", ]


class MatchTypeEnum(Enum):
    """
    Тип совпадения.

    Взято из:
    https://github.com/ImoutoChan/IqdbApi/blob/ef85f9e66a2f90d2c4e5186352a4aaeb11683c70/IqdbApi/SearchResultParser.cs#L261-L273
    """
    SKIP = "Your image"
    BEST = "Best match"
    ADDITIONAL = "Additional match"
    POSSIBLE = "Possible match"
    NO = "No relevant matches"


class MatchRatingEnum(Enum):
    """
    Рейтинг совпадения.

    Взято из:
    https://github.com/ImoutoChan/IqdbApi/blob/ef85f9e66a2f90d2c4e5186352a4aaeb11683c70/IqdbApi/SearchResultParser.cs#L227-L236
    """
    UNRATED = "[Unrated]"
    SAFE = "[Safe]"
    EXPLICIT = "[Explicit]"
    ERO = "[Ero]"


class IqdbResult:
    """
    Результат поиска.
    """

    match_type: str = None
    """
    Тип совпадения.
    """

    preview_link: str = None
    """
    Ссылка на превью картики.
    """

    source_link: str = None
    """
    Ссылка на страницу буры.
    """

    resolution: str = None
    """
    Разрешение найденного оригинала.
    """

    rating: str = None
    """
    Рейтинг найденного оригинала.
    """

    similarity: int = None
    """
    Степень совпадения картинки.
    """

    tags: Optional[List[str]] = None
    """
    Тэги. Их почему-то нет у *Best match* результата.
    """

    def __init__(self, match_type, preview_link, source_link, resolution,
                 rating, similarity, tags):
        self.match_type = match_type
        self.preview_link = preview_link
        self.source_link = source_link
        self.resolution = resolution
        self.rating = rating
        self.similarity = similarity
        self.tags = tags

    def __str(self):
        return "{type}: {sim}%, {res} {rating}; {src}".format(
            type=self.match_type,
            sim=self.similarity,
            res=self.resolution,
            rating=self.rating,
            src=self.source_link
        )

    def __repr__(self):
        return self.__str()

    def __str__(self):
        return self.__str()


class IqdbBooru:
    """
    Бура для поиска и ее статус обновления.
    """

    name: str = None
    """
    Название буры.
    """

    post_update: str = None
    """
    Время последнего обновления постов.
    """

    tag_update: str = None
    """
    Время последнего обновления тегов.
    """

    latest_post: int = None
    """
    Номер последнего поста.
    """

    update_fail_count: Optional[int] = None
    """
    Количество ошибок обновления.
    """

    update_fail_reason: Optional[str] = None
    """
    Причина последней ошибки обновления.
    """

    def __init__(self, name, post_update, tag_update, latest_post,
                 update_fail_count, update_fail_reason):
        self.name = name
        self.post_update = post_update
        self.tag_update = tag_update
        self.latest_post = latest_post
        self.update_fail_count = update_fail_count
        self.update_fail_reason = update_fail_reason

    def __str(self):
        return "{name}: p {post_u}, {post_l}; t {tag}".format(
            name=self.name,
            post_u=self.post_update,
            post_l=self.latest_post,
            tag=self.tag_update
        )

    def __repr__(self):
        return self.__str()

    def __str__(self):
        return self.__str()


class IqdbClient:
    """
    Клиент для https://iqdb.org.

    Результаты получены путем парсинга HTML.
    """

    results_timing: str = None
    """
    Строка со временем выполнения последнего запроса.

    *Searched 14,379,355 images in 3.528 seconds.*
    """

    boorus_status: List[IqdbBooru] = None
    """
    Статус обновления бур.
    """

    def __init__(self):
        self.get_status()

    def get_status(self):
        """
        Получает статус обновления бур.
        """
        response = requests.get(ENDPOINT, params={
            "status": "1"
        })
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "html.parser")
        table_body: Tag = soup.find("table", attrs={
            "style": "white-space: nowrap"
        }).find("tbody")

        result = []
        for entry in table_body.find_all('tr'):
            entry_strings = entry.find_all('td')
            r_name = entry_strings[0].text
            r_post_update = entry_strings[1].text
            r_tag_update = entry_strings[2].text
            r_latest_post = int(entry_strings[3].text)
            update_failure_string: str = entry_strings[4].text
            r_update_fail_count = None
            r_update_fail_reason = None
            if len(update_failure_string) > 0:
                # noinspection PyBroadException
                try:
                    r_update_fail_count = int(
                        FAIL_COUNT_REGEX.search(update_failure_string).group(1)
                    )
                    r_update_fail_reason = FAIL_REASON_REGEX.search(update_failure_string) \
                        .group(1).replace('\n', '')
                except:
                    pass
            booru_instance = IqdbBooru(
                name=r_name,
                post_update=r_post_update,
                tag_update=r_tag_update,
                latest_post=r_latest_post,
                update_fail_count=r_update_fail_count,
                update_fail_reason=r_update_fail_reason
            )
            result.append(booru_instance)
        self.boorus_status = result

    def search(self, picture_path: str) -> List[IqdbResult]:
        """
        Ищет арт на бурах.

        Поддерживаются картинки:

        * PNG, JPEG, GIF
        * < 8192KB
        * < 7500px по каждой стороне

        :param str picture_path: путь до картинки на диске
        :return: ответ сервера
        :rtype: List[IqdbResult]
        """
        with open(picture_path, mode="rb") as file:
            try:
                img: Image.Image = Image.open(file)
            except OSError as exc:
                raise IOError("file is not a picture") from exc
            if img.height >= MAX_SIDE_RESOLUTION or img.width >= MAX_SIDE_RESOLUTION:
                raise RuntimeError("image height or width is larger than 7500px")
            out = BytesIO()
            img.save(out, "PNG", optimize=True)  # Convert any image to supported format
            if out.getbuffer().nbytes > MAX_SIZE:
                raise RuntimeError("image is larger than 8MB")
        # noinspection PyUnboundLocalVariable
        response = requests.post(ENDPOINT, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/64.0.3253.3 Safari/537.36",
        }, files={
            "file": out.getvalue(),
        })

        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "html.parser")

        self.results_timing: Tag = soup.find("p", attrs={
            "style": "font-size: small;",
        }).text

        result: List[IqdbResult] = []

        results_boxes: Tag = soup.find("div", attrs={
            "id": "pages",
            "class": "pages",
        })

        for result_box in results_boxes.find_all('div'):  # Main matches
            info_strings: List[Tag] = result_box.find('table') \
                .find_all('tr')
            match_type = info_strings[0].find('th').text
            if match_type == MatchTypeEnum.SKIP.value:
                continue  # Your image
            if match_type == MatchTypeEnum.NO.value:
                continue  # No relevant matches
            r_match_type = match_type
            links: Tag = info_strings[1].find('td')
            source_link: str = links.find('a')['href']
            r_source_link = 'http:' + source_link if source_link.startswith('//') else source_link
            img_tag: Tag = links.find('a').find('img')
            r_preview_link = ENDPOINT + img_tag['src']
            r_tags = None
            if img_tag.has_attr('title'):
                if ',' in img_tag['title']:
                    split_char = ','
                else:
                    split_char = ' '
                # noinspection PyBroadException
                try:
                    r_tags = img_tag['title'].split('Tags: ')[1].split(split_char)
                except:
                    pass
            res_and_rating = info_strings[3].find('td').text
            r_resolution, r_rating = res_and_rating.split(' ')
            r_similarity = info_strings[4].find('td').text.split('%')[0]

            iqdbresult_instance = IqdbResult(
                match_type=r_match_type,
                preview_link=r_preview_link,
                source_link=r_source_link,
                resolution=r_resolution,
                rating=r_rating,
                similarity=r_similarity,
                tags=r_tags
            )
            result.append(iqdbresult_instance)

        return result
