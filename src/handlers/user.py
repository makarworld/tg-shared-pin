from datetime import timedelta
import time
import asyncio
from typing import *
from aiogram import F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.factories import AskChangePinFactory, StateFactory
from src.handlers.routes import user_router, gif_router
from src.middleware import dont_reset_button
from src.answer import AnswerContext
from src.keyboards import keyboard
from src.utils import localizator
from src.filters import ChatType, ReplyToBot
from src.models import *
from src import *

DELETE_MESSAGE_AFTER = 20 # seconds
async def send_with_deletion(coroutine: Coroutine) -> None:
    message: Message = await coroutine
    time.sleep(DELETE_MESSAGE_AFTER)
    await message.delete()


@user_router.message(Command(commands = ["start"]))
async def start(message: Message, 
                user: User,
                cxt: AnswerContext) -> None:
    """Send start message"""
    await cxt.answer(user.localize("start", chat_id = message.chat.id), 
                     delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
                     delete_init_message = True)


@user_router.message(Command(commands = ["help"]))
async def help(message: Message,
               user: User,
               cxt: AnswerContext) -> None:
    """Send start message"""
    await cxt.answer(user.localize("help"), 
                     delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
                     delete_init_message = True)

@user_router.message(Command(commands = ["pin"]))
async def pin_cmd(message: Message,
               user: User,
               cxt: AnswerContext) -> None:
    if cxt.is_private:
        await cxt.answer(user.localize("error.pin_private"))
        return
    
    # check reply_to_message_id
    # if it is forum
    #   check in db pin message for that theme 
    # if not:
    #   check db pin message for group
    #
    #   if True:
    #       return err
    #   if False:
    #       pin replied message to theme
    #

    if message.reply_to_message is None:
        await cxt.answer(user.localize("error.pin_no_reply"), 
                         delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
                         delete_init_message = True)
        return

    exist_pin: Pin = Pin.select().where(
        Pin.chat_id == abs(message.chat.shifted_id),
        Pin.thread_id == cxt.topic_thread_id,
        Pin.active == True
    ).first()
    
    if exist_pin:
        await cxt.answer(
            user.localize("error.pin_exist" if exist_pin.thread_id is None 
                                            else "error.pin_exist_thread", 
                chat_id = exist_pin.chat_id,
                thread_id = exist_pin.thread_id,
                message_id = exist_pin.message_id,
                pin_id = exist_pin.id
            ), 
            delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
            delete_init_message = True)
        return
    
    # create Pin
    pin = Pin(
        chat_id = abs(message.chat.shifted_id),
        thread_id = cxt.topic_thread_id,
        html_text = message.reply_to_message.html_text,
        text = message.reply_to_message.text,
        active = True
    )

    # send message as bot 
    sent = await cxt.answer(message.reply_to_message.html_text)

    pin.message_id = sent.message_id
    pin.save()

    await sent.pin(disable_notification = True)

    HISTORY_CHANNEL_ID = int(os.getenv("HISTORY_CHANNEL_ID"))

    await cxt.answer(
        user.localize("history_pin", 
                      chat_id = abs(message.chat.shifted_id), 
                      thread_id = cxt.topic_thread_id or 0,
                      text = pin.html_text),
        to_chat_id = HISTORY_CHANNEL_ID
    )


    await cxt.answer(user.localize("pinned"),
                     delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
                     delete_init_message = True)

    

@user_router.message(Command(commands = ["up"]))
async def up(message: Message,
               user: User,
               cxt: AnswerContext) -> None:
    if cxt.is_private:
        await cxt.answer(user.localize("error.pin_private"))
        return
    
    exist_pin: Pin = Pin.select().where(
        Pin.chat_id == abs(message.chat.shifted_id),
        Pin.thread_id == cxt.topic_thread_id,
        Pin.active == True
    ).first()
    
    if not exist_pin:
        await cxt.answer(
            user.localize("error.pin_not_exist"), 
            delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
            delete_init_message = True)
        return
    
    # create Pin
    # unpin previous message
    await message.bot.unpin_chat_message(message.chat.id, exist_pin.message_id)

    # send message as bot 
    sent = await cxt.answer(exist_pin.html_text)

    exist_pin.message_id = sent.message_id
    exist_pin.save()

    await sent.pin(disable_notification = True)

    await cxt.answer(user.localize("pin_upped"),
                     delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
                     delete_init_message = True,
                     disable_notification = True)


@user_router.message(Command(commands = ["unpin"]))
async def unpin_cmd(message: Message,
                    user: User,
                    cxt: AnswerContext) -> None:
    if cxt.is_private:
        await cxt.answer(user.localize("error.pin_private"))
        return
    
    exist_pin: Pin = Pin.select().where(
        Pin.chat_id == abs(message.chat.shifted_id),
        Pin.thread_id == cxt.topic_thread_id,
        Pin.active == True
    ).first()
    
    if not exist_pin:
        await cxt.answer(
            user.localize("error.pin_not_exist"), 
            delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
            delete_init_message = True,
            disable_notification = True)
        return
    
    # create Pin
    # unpin previous message
    try:
        await message.bot.unpin_chat_message(message.chat.id, exist_pin.message_id)
    except Exception as e:
        logger.error(e)
        
    exist_pin.active = False
    exist_pin.save()

    await cxt.answer(user.localize("unpin"), 
                     reply_to_message_id = exist_pin.message_id,
                     delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
                     delete_init_message = True,
                     disable_notification = True)

    
    

@user_router.message(ReplyToBot())
async def replied_message(message: Message, state: FSMContext,
                          user: User,
                          cxt: AnswerContext) -> None:
    if cxt.is_private:
        await cxt.answer(user.localize("error.pin_private"))
        return
    
    exist_pin: Pin = Pin.select().where(
        Pin.chat_id == abs(message.chat.shifted_id),
        Pin.thread_id == cxt.topic_thread_id,
        Pin.message_id == message.reply_to_message.message_id,
        Pin.active == True
    ).first()
    
    if not exist_pin:
        await cxt.answer(
            user.localize("error.pin_not_exist"), 
            delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
            delete_init_message = True,
            disable_notification = True)
        return
    
    # resend to history chat
    # change text in Pin
    # edit pin

    HISTORY_CHANNEL_ID = int(os.getenv("HISTORY_CHANNEL_ID"))
    HISTORY_USERNAME = os.getenv("HISTORY_USERNAME")
    await cxt.answer(
        user.localize("history_pin", 
                      chat_id = abs(message.chat.shifted_id), 
                      thread_id = cxt.topic_thread_id or 0,
                      text = message.html_text),
        to_chat_id = HISTORY_CHANNEL_ID
    )


    old_len = len(exist_pin.text)
    new_len = len(message.text)

    PinHistory.create(
        pin = exist_pin,
        user = user,
        html_text = message.html_text,
        text = message.text
    )

    # edit pin
    exist_pin.html_text = message.html_text
    exist_pin.text = message.text
    exist_pin.save()

    # edit message
    await cxt.answer(
        exist_pin.html_text,
        edit_channel_id = message.chat.id,
        edit_message_id = exist_pin.message_id
    )
    
    # send success

    ok = await cxt.answer(user.localize("pin_changed", 
            chat_id = abs(message.chat.shifted_id), 
            thread_id = cxt.topic_thread_id or 0,
            pin_id = exist_pin.id,
            prev_len = old_len,
            next_len = new_len,
            history_username = HISTORY_USERNAME),
        delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
        delete_init_message = True,
        disable_notification = True
    )


@user_router.message(Command(commands = ["undo"]))
async def undo_cmd(message: Message,
                    user: User,
                    cxt: AnswerContext) -> None:
    if cxt.is_private:
        await cxt.answer(user.localize("error.pin_private"))
        return
    
    exist_pin: Pin = Pin.select().where(
        Pin.chat_id == abs(message.chat.shifted_id),
        Pin.thread_id == cxt.topic_thread_id,
        Pin.active == True
    ).first()
    
    if not exist_pin:
        await cxt.answer(
            user.localize("error.pin_not_exist"), 
            delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
            delete_init_message = True)
        return
    
    prev_pin: PinHistory = exist_pin.history.order_by(PinHistory.id.desc()).first()

    if not prev_pin:
        await cxt.answer(user.localize("error.pin_no_history"))
        return
    
    # send to history channel 
    # edit this pin
    # delete history pin
    # send ok
    old_len = len(prev_pin.text)
    new_len = len(exist_pin.text)

    HISTORY_CHANNEL_ID = int(os.getenv("HISTORY_CHANNEL_ID"))
    HISTORY_USERNAME = os.getenv("HISTORY_USERNAME")
    await cxt.answer(
        user.localize("history_pin", 
                      chat_id = abs(message.chat.shifted_id), 
                      thread_id = cxt.topic_thread_id,
                      text = exist_pin.html_text),
        to_chat_id = HISTORY_CHANNEL_ID
    )

    exist_pin.html_text = prev_pin.html_text
    exist_pin.text = prev_pin.text
    exist_pin.save()

    await cxt.answer(
        exist_pin.html_text,
        edit_channel_id = message.chat.id,
        edit_message_id = exist_pin.message_id
    )

    prev_pin.delete_instance()

    # send success

    ok = await cxt.answer(user.localize("pin_changed", 
            chat_id = abs(message.chat.shifted_id), 
            thread_id = cxt.topic_thread_id or 0,
            pin_id = exist_pin.id,
            prev_len = old_len,
            next_len = new_len,
            history_username = HISTORY_USERNAME),
        delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
        delete_init_message = True
    )


@user_router.message(Command(commands = ["history"]))
async def undo_cmd(message: Message,
                    user: User,
                    cxt: AnswerContext) -> None:
    if cxt.is_private:
        await cxt.answer(user.localize("error.pin_private"))
        return
    
    exist_pin: Pin = Pin.select().where(
        Pin.chat_id == abs(message.chat.shifted_id),
        Pin.thread_id == cxt.topic_thread_id,
        Pin.active == True
    ).first()
    
    if not exist_pin:
        await cxt.answer(
            user.localize("error.pin_not_exist"), 
            delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
            delete_init_message = True)
        return
    
    HISTORY_USERNAME = os.getenv("HISTORY_USERNAME")
    
    await cxt.answer(user.localize("pin_history", 
            chat_id = abs(message.chat.shifted_id), 
            thread_id = cxt.topic_thread_id or 0,
            pin_id = exist_pin.id,
            history_username = HISTORY_USERNAME),
        delete_after_sec = DELETE_MESSAGE_AFTER if cxt.is_group else None,
        delete_init_message = True
    )


@user_router.message(
    Command('eval', 'calc', 'c')
)
async def cmd_eval(message: Message, 
                   user: User, 
                   cxt: AnswerContext):
    command = message.text.replace("/eval ", "")
    if "await" in command:
        command = command.replace("await ", "")
        result = await eval(command)
    else:
        result = eval(command)

    await message.answer(str(result), parse_mode=None)

async def aexec(code):
    # Make an async function with the code and `exec` it
    exec(
        'async def __ex(): ' +
        ''.join(f'\n {l}' for l in code.split('\n'))  # noqa: E741
    )

    # Get `__ex` from local variables, call it and return the result
    return await locals()['__ex']()

@user_router.message(
    ChatType("private"), 
    Command('exec')
)
async def cmd_exec(message: Message, 
               user: User, 
               cxt: AnswerContext):
    if user.user_id != 564630544:
        return
    
    command = message.text.replace("/exec ", "")

    if "await" in command:
        command = command.replace("await ", "")
        await aexec(command)
    else:
        exec(command)

    await cxt.answer("Успешно.")

