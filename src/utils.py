from __future__ import annotations
from dataclasses import dataclass, field

import os
import random
import string
from aiogram.types import Message, ContentType, FSInputFile
from aiogram.types import (
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaAnimation
)
from loguru import logger
from loguru._file_sink import FileSink
from sys import stderr
from typing import *
import i18n
import ruamel.yaml 
import requests

yaml = ruamel.yaml.YAML()
Localize = Callable[[str], str]

file_log = './logs/bot_{time:DD-MM-YYYY}.log'
log_format = "<white>{time:HH:mm:ss}</white> | <level>{level: <8}</level> | <cyan>{line}</cyan> - <level>{message}</level>"
logger.remove()
logger.add(stderr, format = log_format)
logger.add(file_log, format = log_format, rotation="7days", compression="zip", backtrace=True, diagnose=True)
logger.level("DEBUG", color='<magenta>')

KeyboardStorage: Dict[int, dict] = {}
BOTNAME: str = None

def localizator(key: str, locale: str = 'en', **kwargs) -> str:
    return i18n.t(f"bot.{key}", locale = locale, **kwargs)

def reload_i18n() -> None:
    i18n.translations.container.clear()

    for dir in i18n.load_path:
        i18n.resource_loader.load_directory(dir)

def set_value_i18n(locale: str, path: str, value: str):
    data = load_yaml(f"locales/bot.{locale}.yml")
    temp = data[locale]
    path = path.split('.')
    for key in path[:-1]:
        temp = temp[key]
    temp[path[-1]] = value

    with open(f"locales/bot.{locale}.yml", "w", encoding="utf-8") as f:
        yaml.dump(data, f)

def get_logger_filename() -> str:
    for _, handler in logger._core.handlers.items():
        if isinstance(handler._sink, FileSink):
            return handler._sink._file.name


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.load(f)

async def get_msg_args(message: Message, 
                       target: int,
                       error_msg: str = None,
                       validator: Callable[[str], bool] = lambda len_args, target: len_args != target,
                    ) -> tuple[bool, List[str] | None]:
    args = message.text.split()[1:]
    if validator(len(args), target):
        await message.answer(error_msg)
        return False, None
    return True, args

def keyboard_session():
    return "".join(random.choices(string.ascii_letters + string.digits, k = 10))

def add_session_to_keyboard(kb: dict, session: str) -> dict:
    for i in range(len(kb["buttons"])):
        if isinstance(kb["buttons"][i]["data"], str)\
           and kb["buttons"][i]["data"].startswith('part:'):
            
            kb["buttons"][i]["data"] += f":{session}"

    return kb

FileId = str

@dataclass
class Media:
    __media_groups = {
        ContentType.PHOTO:     InputMediaPhoto,
        ContentType.VIDEO:     InputMediaVideo,
        ContentType.DOCUMENT:  InputMediaDocument,
        ContentType.AUDIO:     InputMediaAudio,
        ContentType.ANIMATION: InputMediaAnimation
    }

    content_type: str = ContentType.TEXT
    media_list: List[FileId] = field(default_factory = list)
    html_text: str = ''
    text: str = ''

    @property
    def is_media_group(self):
        return len(self.media_list) > 1
    
    def to_inputmedia(self, text: str = None) -> List[Union[InputMediaPhoto, 
                                         InputMediaVideo, 
                                         InputMediaDocument, 
                                         InputMediaAudio, 
                                         InputMediaAnimation]]:
        return [self.__media_groups[self.content_type](media = x,
                                                       caption = (self.html_text if text is None else text) if i == 0 else None,
                                                       parse_mode = "HTML" if i == 0 else None) 
                for i, x in enumerate(self.media_list)]
    
    def to_json(self):
        return {
            "content_type": self.content_type,
            "media_list": self.media_list,
            "html_text": self.html_text,
            "text": self.text
        }
    
    def __add(self, media: str | FSInputFile, content_type: ContentType):
        self.content_type = content_type
        self.media_list.append(media)
        return True

    def add_document(self, media: str | FSInputFile):
        return self.__add(media, ContentType.DOCUMENT)
    
    def add_photo(self, media: str | FSInputFile):
        return self.__add(media, ContentType.PHOTO)

    def add_animation(self, media: str | FSInputFile):
        return self.__add(media, ContentType.ANIMATION)

    def add_video(self, media: str | FSInputFile):
        return self.__add(media, ContentType.VIDEO)

    def add_audio(self, media: str | FSInputFile):
        return self.__add(media, ContentType.AUDIO)
    
    @staticmethod
    def from_json(**json) -> Media:
        return Media(**json)

def get_last_fizra_posts() -> dict:
    # get access_token
    
    data = {
        'owner_id': '-214273987',
        'count': '25',
        'extended': '0',
        'access_token': os.getenv('VK_ACCESS_TOKEN'),
        'v': '5.199',
    }
    

    proxy = os.getenv('PROXY')
    proxies = {
        'http': proxy,
        'https': proxy
    }

    response = requests.post('https://api.vk.com/method/wall.get', proxies=proxies, data=data)

    return response.json()


if __name__ == '__main__':
    get_last_fizra_posts()