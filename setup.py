# -*- coding: utf-8 -*-
"""
Setup script.
"""
from distutils.core import setup

from setuptools import find_packages

with open('README.rst') as file:
    readme = file.read()

setup(
    name='pod042-bot',
    version='0.0.1.0',
    description='Kawaii Telegram bot!',
    long_description=readme,
    author='saber-nyan',
    author_email='saber-nyan@ya.ru',
    url='https://github.com/saber-nyan/pod042-bot',
    license='Apache 2.0',
    install_requires=[
        'pyTelegramBotAPI',
    ],
    packages=find_packages()
)
