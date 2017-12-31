# -*- coding: utf-8 -*-
"""
Звук soundboard для inline-постинга.
"""
import json


class InlineSound:
    """
    Звук soundboard.
    """
    full_url: str
    category: str
    pretty_name: str

    def __init__(self, json_entry: json):
        self.__dict__.update(json_entry)

    def __str(self):
        return "<url: {}; {}, {}>".format(self.full_url, self.category,
                                          self.pretty_name)

    def __str__(self):
        return self.__str()

    def __repr__(self):
        return self.__str()
