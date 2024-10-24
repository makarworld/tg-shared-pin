import asyncio
import inspect
from aiogram.filters.callback_data import CallbackData
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup

from src.utils import *
from src.models import *
from src.keyboards import keyboard
from src.factories import CallbackFactory

class AnswerContext:
    def __init__(self, message: Message, user: User, data: dict):
        self._message = message
        self.user = user
        self.data = data 

    @property
    def is_private(self) -> Message:
        return self._message.chat.type == "private"

    @property
    def is_group(self) -> Message:
        return self._message.chat.type in ("group", "supergroup")
    
    @property
    def topic_thread_id(self) -> int:
        return self._message.message_thread_id if self._message.chat.is_forum else None

    @property
    def callback_data(self) -> str | None:
        if isinstance(self._message, CallbackQuery):
            return self._message.data
        return None

    async def reset_button(self):
        """
        Respond clicked button if event is CallbackQuery
        """
        if isinstance(self._message, CallbackQuery):
            await self._message.answer()

    def create_keyboard(self, kb_route: str, data_factory: CallbackData = CallbackFactory, **formats: str) -> InlineKeyboardMarkup:
        return keyboard.create(kb_route, self.user.localize, data_factory=data_factory, **formats)

    def build_keyboard(self, config: List[List[dict]], **formats: str) -> InlineKeyboardMarkup:
        return keyboard._build_keyboard(config, self.user.localize, **formats)

    async def redirect(self, function: Awaitable[Callable], *args, **kwargs) -> Any:
        params = inspect.getfullargspec(function)
        kwargs.update(self.data)
        
        # delete kwargs if not needed to func
        kwargs = {k: v for k, v in kwargs.items() if k in params.args}

        # if event provided, replace self._message with it
        if kwargs.get("message") or kwargs.get("callback"):
            event = kwargs.pop("message") or kwargs.pop("callback")
        else:
            event = self._message

        return await function(event, *args, **kwargs)

    async def answer(self,
                     text: str, 
                     reply_markup: InlineKeyboardMarkup = None,
                     to_chat_id: int = None,
                     parse_mode: str = "HTML",
                     reply_to_message_id: int = None,
                     edit_channel_id: int = None,
                     edit_message_id: int = None,
                     disable_notification: bool = None,
                     media: Media = None,
                     skip_error: bool = False,
                     delete_after_sec: int = None,
                     delete_init_message: bool = False,
                     **formats: dict) -> Message:
        
        if delete_init_message:
            # try to delete
            try:
                await self._message.delete()
            except Exception:
                pass

        if delete_after_sec:
            # second loop of sending message
            sendend: Message = await self.answer(text, 
                                                 reply_markup, 
                                                 to_chat_id, 
                                                 parse_mode, 
                                                 reply_to_message_id, 
                                                 edit_channel_id, 
                                                 edit_message_id, 
                                                 disable_notification, 
                                                 media, skip_error, 
                                                 delete_after_sec = None,
                                                 **formats)

            await asyncio.sleep(delete_after_sec)

            if sendend:
                # try to delete
                try:
                    await sendend.delete()
                except Exception:
                    pass
            
            return sendend

        if not self._message:
            raise Exception("No message to answer")
        
        try:
            if isinstance(self._message, CallbackQuery):
                message = self._message.message
            else:
                message = self._message

            if media:
                if message.content_type != media.content_type:
                    # will send new message instead of edit
                    to_chat_id = message.chat.id

            text = text.format(**formats) if formats else text
            if not to_chat_id:
                # edit text for any message
                if edit_channel_id and edit_message_id:
                    if media and media.content_type != ContentType.TEXT.value:
                        return await message.bot.edit_message_caption(
                            caption = text,
                            chat_id = edit_channel_id, 
                            message_id = edit_message_id, 
                            parse_mode = parse_mode,
                            reply_markup = reply_markup,
                        )

                    return await message.bot.edit_message_text(
                        text = text, 
                        chat_id = edit_channel_id, 
                        message_id = edit_message_id, 
                        parse_mode = parse_mode, 
                        disable_web_page_preview = True,
                        reply_markup = reply_markup,
                    )
                
                elif isinstance(self._message, Message):
                    if media and media.content_type != ContentType.TEXT.value:
                        if media.is_media_group:
                            return await message.answer_media_group(
                                media = media.to_inputmedia(text),
                                disable_notification = disable_notification,
                                reply_to_message_id = reply_to_message_id,
                            )

                        return await message.__getattribute__(f"answer_{media.content_type.lower()}")(
                            **{media.content_type.lower(): media.media_list[0]},
                            caption = text,
                            parse_mode = "HTML",
                            disable_notification = disable_notification,
                            reply_to_message_id = reply_to_message_id,
                            reply_markup = reply_markup,
                        )
                        
                    return await message.answer(
                        text = text, 
                        parse_mode = parse_mode, 
                        disable_web_page_preview = True,
                        reply_markup = reply_markup,
                        disable_notification = disable_notification
                    )
                
                elif isinstance(self._message, CallbackQuery):
                    if media and media.content_type != ContentType.TEXT.value:
                        return await message.bot.edit_message_caption(
                            caption = text,
                            chat_id = edit_channel_id, 
                            message_id = edit_message_id, 
                            parse_mode = parse_mode,
                            reply_markup = reply_markup,
                        )
                    return await message.edit_text(
                        text = text, 
                        parse_mode = parse_mode, 
                        disable_web_page_preview = True,
                        reply_markup = reply_markup,
                    )
            else:
                if media and media.content_type != ContentType.TEXT.value:
                    if media.is_media_group:
                        if reply_markup is not None:
                            logger.warning("Function utils.py:answer_message() got reply_markup, but reply markup is not supported for media groups. It will be skipped.")
                        
                        return await message.bot.send_media_group(
                            to_chat_id,
                            media = media.to_inputmedia(text),
                            disable_notification = disable_notification,
                            reply_to_message_id = reply_to_message_id,
                        )

                    return await message.bot.__getattribute__(f"send_{media.content_type.lower()}")(
                        to_chat_id,
                        **{media.content_type.lower(): media.media_list[0]},
                        caption = text,
                        parse_mode = "HTML",
                        disable_notification = disable_notification,
                        reply_to_message_id = reply_to_message_id,
                        reply_markup = reply_markup,
                    )

                return await message.bot.send_message(
                    to_chat_id,
                    text = text, 
                    parse_mode = parse_mode, 
                    disable_web_page_preview = True,
                    reply_markup = reply_markup,
                    reply_to_message_id = reply_to_message_id,
                    disable_notification = disable_notification
                )

        #except MessageNotModified: 
        #    pass

        except Exception as e:
            if not skip_error:
                logger.exception(e)
                logger.error(f"Received error while processing message: {text}")#
