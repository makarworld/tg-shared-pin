from __future__ import annotations
from aiogram import Bot
from redis.asyncio.client import Redis as AsyncRedis
from playhouse.postgres_ext import *
from aiogram.types import Message
from playhouse.migrate import *
from datetime import datetime, timedelta
from functools import partial
from enum import Enum
from typing import *
from peewee import *
import subprocess
import os 

from src.utils import Localize, localizator, logger

REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = int(os.getenv('REDIS_PORT'))
REDIS_DB = int(os.getenv('REDIS_DB'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
#
DB_NAME = os.getenv('POSTGRES_DB', 'postgres')
DB_USER = os.getenv('POSTGRES_USER', 'postgres')
DB_PASS = os.getenv('POSTGRES_PASSWORD', 'postgres')
DB_HOST = os.getenv('POSTGRES_HOST', 'postgres')
DB_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
#
DEBUG = os.getenv("DEBUG") == "true"
IS_DOCKER = os.getenv("DOCKER") == "true"
USE_SQLITE = os.getenv("USE_SQLITE") == "true"

if not IS_DOCKER:
    logger.warning("Running not in Docker. Redis and Postgres hosts was redefined to localhost.")
    if DB_HOST == "postgres":
        DB_HOST = "localhost"
        
    if REDIS_HOST == "redis":
        REDIS_HOST = "localhost"

# Connect redis
async_redis = AsyncRedis(
    password = REDIS_PASSWORD,
    host     = REDIS_HOST,
    port     = REDIS_PORT, 
    db       = REDIS_DB
)

db = DatabaseProxy()

def get_main_db():
    if not USE_SQLITE:
        # Connect Postgres
        return PostgresqlExtDatabase(
            database = DB_NAME,
            user     = DB_USER,
            password = DB_PASS,
            host     = DB_HOST,
            port     = DB_PORT
        )
    else:
        logger.warning("USE_SQLITE is true. Using SQLite as main database.")
        return SqliteDatabase('database.db')

db.initialize(get_main_db())

class BaseModel(Model):
    id: int
    class Meta:
        database = db

class UserRole(Enum):
    """
    User access roles
    """
    USER      = 0
    MODERATOR = 1
    ADMIN     = 2
    OWNER     = 4

class BookType(str, Enum):
    """
    Book type for generate universal keyboard pagination
    """
    ONE = "one"
    MANY = "many"

class User(BaseModel): 
    id:               int 
    user_id:          int             = BigIntegerField(unique = True)
    username:         str             = CharField(null = True)
    first_name:       str             = CharField(null = True)
    last_name:        str             = CharField(null = True)
    #
    language:         str             = CharField(default = "ru")
    #
    role:             int             = IntegerField(default = UserRole.USER.value)
    entrance_time:    datetime        = DateTimeField(default = datetime.utcnow)
    ban:              bool            = BooleanField(default = False)

    def __str__(self) -> str:
        return f"User[{self.id}] <{self.user_id} @{self.username} `{self.first_name} {self.last_name}`>"

    def __repr__(self) -> str:
        return self.__str__()

    @staticmethod
    def g(*args, **kwargs) -> User | None:
        return User.get_or_none(*args, **kwargs)

    @property
    def localize(self) -> Localize:
        return partial(localizator, locale = self.language or "en") 

    @property
    def mention(self) -> str:
        return f"<code>{self.first_name if self.first_name else ''}{' ' + self.last_name if self.last_name else ''}</code> <a href=\"tg://user?id={self.user_id}\">{self.user_id}</a> (@{self.username})"

class Pin(BaseModel):
    chat_id: int = IntegerField()
    thread_id: int = IntegerField(null = True)
    message_id: int = IntegerField(null = True)
    html_text: str = TextField()
    text: str = CharField()
    active: bool = BooleanField(default = True)
    #
    buttons: List[PinButton]
    history: List[PinHistory]

    @property
    def reply_markup(self) -> ...:
        return

class PinHistory(BaseModel):
    pin: Pin = ForeignKeyField(Pin, backref = "history")
    user: User = ForeignKeyField(User, backref = "actions")
    html_text: str = TextField()
    text: str = CharField()

    buttons: List[PinButton]
    
class PinButton(BaseModel):
    pin: Pin = ForeignKeyField(Pin, backref = "buttons", null = True)
    histored_pin: PinHistory = ForeignKeyField(PinHistory, backref = "buttons", null = True)
    text: str = CharField()
    url: str = CharField()
    enabled: bool = BooleanField(default = True)


User.create_table(safe = True)
Pin.create_table(safe = True)
PinHistory.create_table(safe = True)
PinButton.create_table(safe = True)

async def renv(key: str, value: str | bool = None) -> str | bool | None:
    if value is None:
        current_value = await async_redis.get(key)
        current_value = current_value.decode() if current_value else None

        if current_value in ["true", "false"]:
            current_value = current_value == "true"

        return current_value
    else:
        if isinstance(value, bool):
            value = "true" if value else "false"

        await async_redis.set(key, value)
        logger.warning(f"[RENV] Set {key}={value}")
