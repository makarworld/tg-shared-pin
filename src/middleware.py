from __future__ import annotations
import os
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, ContentType, FSInputFile
import redis.asyncio.client 
from typing import *
import asyncio
import time


from src.answer import AnswerContext
from src.utils import Media, localizator, get_logger_filename, logger
from src.models import User


def dont_reset_button(func):
    setattr(func, 'dont_reset_button', True)

    async def decorator(*args, **kwargs):
        return await func(*args, **kwargs)

    return decorator

def rate_limit(limit: int, key = None):
    """
    Decorator for configuring rate limit and key in different functions.

    :param limit:
    :param key:
    :return:
    """

    def decorator(func):
        setattr(func, 'throttling_rate_limit', limit)
        if key:
            setattr(func, 'throttling_key', key)
        return func

    return decorator

class ThrottlingMiddleware(BaseMiddleware):
    medias = {}

    def __init__(self, redis: redis.asyncio.client.Redis, limit = .5, key_prefix = 'antiflood_'):
        self.rate_limit = limit
        self.prefix = key_prefix
        self.throttle_manager = ThrottleManager(redis = redis)

        super(ThrottlingMiddleware, self).__init__()


    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:

        if isinstance(event, Message) and event.media_group_id:
            try:
                self.medias[event.media_group_id].append(event)
                return
            except KeyError:
                self.medias[event.media_group_id] = [event]
                await asyncio.sleep(1)

                media_events: List[Union[Message, CallbackQuery]] = self.medias.pop(event.media_group_id)
                media = Media(content_type = event.content_type, media_list = [], html_text = '', text = '')
                if media.content_type in (
                    ContentType.PHOTO,
                    ContentType.DOCUMENT,
                    ContentType.VIDEO,
                    ContentType.AUDIO,
                    ContentType.ANIMATION
                ):
                    for e in media_events:
                        if e.html_text:
                            media.html_text = e.html_text
                            media.text = e.text if e.text else e.caption

                        if e.content_type == ContentType.PHOTO:
                            file_id = e.photo[-1].file_id
                        else:
                            file_id = e.__getattribute__(e.content_type.lower()).file_id
                        media.media_list.append(file_id)

                data["media_events"] = media_events
                data["media"] = media

        elif isinstance(event, Message) and event.content_type in (
                    ContentType.PHOTO,
                    ContentType.DOCUMENT,
                    ContentType.VIDEO,
                    ContentType.AUDIO,
                    ContentType.ANIMATION,
                    ContentType.VOICE,
                    ContentType.VIDEO_NOTE
                ):

            data["media"] = Media(
                content_type = event.content_type,
                media_list = [event.__getattribute__(event.content_type.lower()).file_id if not event.content_type == ContentType.PHOTO else event.photo[-1].file_id],
                html_text = event.html_text,
                text = event.text if event.text else event.caption
            )

        # check if it pin by that bot -> delete it
        if event.content_type == ContentType.PINNED_MESSAGE and event.from_user.id == event.bot.id:
            await event.delete()
            return 
        
        try:
            await self.on_process_event(event, data["handler"])
            await self.check_event(event, data)
        except CancelHandler:
            # Cancel current handler
            return
        
        result = None 
        try:
            result = await handler(event, data)
        except Exception as e:
            logger.exception(e)

            owner_id = int(os.getenv("OWNER_ID"))
            await event.bot.send_document(
                chat_id = owner_id,
                caption = localizator("handler_exception", 
                            module = data['handler'].callback.__module__,
                            name = data['handler'].callback.__name__,
                            err = str(e).replace("<", "^").replace(">", "^"),
                            #
                            locale = 'ru'
                ),
                document = FSInputFile(get_logger_filename())
            )


        return result 

    async def check_event(self, message: Union[Message, CallbackQuery], data: dict):
        
        if message.from_user.id == message.bot.id:
            # if self event 
            return

        # find user
        user: User = User.select().where(User.user_id == message.from_user.id).first()
        
        if not user:
            # if not finded -> create
            user = User.create(
                user_id = message.from_user.id,
                username = message.from_user.username,
                first_name = message.from_user.first_name,
                last_name = message.from_user.last_name
            )


        # update username/first_name if user changed it
        if user.username != message.from_user.username or\
           user.first_name != message.from_user.first_name or\
           user.last_name != message.from_user.last_name:

            user.username = message.from_user.username
            user.first_name = message.from_user.first_name
            user.last_name = message.from_user.last_name

            user.save()

        # log message

        if isinstance(message, Message):
            logger.info(f"User {message.from_user.id} ({message.from_user.username}) sent message: {message.text if message.text else message.caption}")
        else:
            logger.info(f"User {message.from_user.id} ({message.from_user.username}) sent callback: {message.data}")

        # if ban - not process
        if user.ban: 
            raise CancelHandler()

        cxt = AnswerContext(message, user = user, data = data)

        dont_reset = getattr(data["handler"].callback, "dont_reset_button", False)
        if dont_reset is False:
            await cxt.reset_button()

        # add kwargs to handler
        data["user"] = user
        data["cxt"] = cxt


    async def on_process_event(
        self, 
        event: Union[Message, CallbackQuery],
        handler: Callable[[Union[Message, CallbackQuery], Awaitable[Any]]],
    ) -> Any:

        if isinstance(event, Message):
            chat_id = event.chat.id
            chat_type = event.chat.type
        else:
            chat_id = event.message.chat.id
            chat_type = event.message.chat.type

        if chat_type != "private":
            return
        
        limit = getattr(handler.callback, "throttling_rate_limit", self.rate_limit)
        key = getattr(handler.callback, "throttling_key", f"{self.prefix}_message")

        # Use ThrottleManager.throttle method.
        try:
            await self.throttle_manager.throttle(key, rate = limit, user_id = event.from_user.id, chat_id = chat_id)
        except Throttled as t:
            # Execute action
            await self.event_throttled(event, t)

            # Cancel current handler
            raise CancelHandler()

    async def event_throttled(self, event: Union[Message, CallbackQuery], throttled: Throttled):
        # Calculate how many time is left till the block ends
        delta = throttled.rate - throttled.delta
        ...
        # Prevent flooding

        if throttled.exceeded_count <= 2 and isinstance(event, CallbackQuery):
            await event.answer(f'Too many events.\nTry again in {delta:.2f} seconds.')


class ThrottleManager:
    bucket_keys = [
        "RATE_LIMIT", "DELTA",
        "LAST_CALL", "EXCEEDED_COUNT"
    ]
    def __init__(self, redis: redis.asyncio.client.Redis):
        self.redis = redis

    async def throttle(self, key: str, rate: float, user_id: int, chat_id: int):
        now = time.time()
        bucket_name = f'throttle_{key}_{user_id}_{chat_id}'

        data = await self.redis.hmget(bucket_name, self.bucket_keys)
        data = {
            k: float(v.decode()) 
               if isinstance(v, bytes) 
               else v 
            for k, v in zip(self.bucket_keys, data) 
            if v is not None
        }

        # Calculate
        called = data.get("LAST_CALL", now)
        delta = now - called
        result = delta >= rate or delta <= 0

        # Save result
        data["RATE_LIMIT"] = rate
        data["LAST_CALL"] = now
        data["DELTA"] = delta
        if not result:
            data["EXCEEDED_COUNT"] += 1
        else:
            data["EXCEEDED_COUNT"] = 1

        await self.redis.hmset(bucket_name, data)

        if not result:
            raise Throttled(key=key, chat=chat_id, user=user_id, **data)
        
        return result

class Throttled(Exception):
    def __init__(self, **kwargs):
        self.key = kwargs.pop("key", '<None>')
        self.called_at = kwargs.pop("LAST_CALL", time.time())
        self.rate = kwargs.pop("RATE_LIMIT", None)
        self.exceeded_count = kwargs.pop("EXCEEDED_COUNT", 0)
        self.delta = kwargs.pop("DELTA", 0)
        self.user = kwargs.pop('user', None)
        self.chat = kwargs.pop('chat', None)

    def __str__(self):
        return f"Rate limit exceeded! (Limit: {self.rate} s, " \
               f"exceeded: {self.exceeded_count}, " \
               f"time delta: {round(self.delta, 3)} s)"

class CancelHandler(Exception):
    pass