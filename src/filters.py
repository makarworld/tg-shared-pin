from typing import *
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Filter

from src.models import *

class Role(Filter):
    def __init__(self, role: UserRole):
        self.role = role

    async def __call__(self, message: Message | CallbackQuery) -> bool:
        uid = message.from_user.id if isinstance(message, Message) else message.from_user.id
        
        user: User | None = User.select().where(User.user_id == uid).first()
        if user and user.role >= self.role:
            return True
        return False

class ChatType(Filter):
    def __init__(self, *type: str, exclude: List[str] = []):
        self.types = type
        self.exclude = exclude

    async def __call__(self, message: Message | CallbackQuery) -> bool:
        return message.chat.type in self.types and message.chat.type not in self.exclude if isinstance(message, Message)\
          else message.message.chat.type in self.types and message.message.chat.type not in self.exclude


class ReplyToBot(Filter):
    async def __call__(self, message: Message | CallbackQuery) -> bool:
        return message.reply_to_message != None and message.reply_to_message.from_user.id == message.bot.id