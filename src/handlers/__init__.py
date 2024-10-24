import glob
from aiogram import Bot, Dispatcher
from aiogram.types import Message, BotCommand, BotCommandScopeChat, FSInputFile
from aiogram.fsm.storage.redis import RedisStorage
import os

from src.utils import logger
from src.models import User, async_redis
from src.middleware import ThrottlingMiddleware

dp = Dispatcher(
    storage = RedisStorage(redis = async_redis), 
)
dp.message.middleware(ThrottlingMiddleware(async_redis, limit = 0.5))
dp.callback_query.middleware(ThrottlingMiddleware(async_redis, limit = 0.5))

main_commands = [
    #BotCommand(command = "start", description = "Главное меню / Main menu"),
    #BotCommand(command = "help", description = "Главное меню / Main menu"),
]

admin_commands = [
    #BotCommand(command = "help", description = "Список команд"),
    #BotCommand(command = "mailing", description = "Рассылка"),
    #BotCommand(command = "user", description = "Информация по пользователю"),
    #BotCommand(command = "update_sheets", description = "Обновить данные в таблице"),
    #BotCommand(command = "update_referrals", description = "Обновить данные о рефералке"),
    #BotCommand(command = "promos", description = "Список активных промокодов"),
    #BotCommand(command = "all_promos", description = "Список всех промокодов"),
    #BotCommand(command = "create_promo", description = "Создать промокод"),
    #BotCommand(command = "edit_promo", description = "Редактировать промокод"),
    #BotCommand(command = "lics", description = "Статистика лицензий"),
]

TECH_WORKS = os.getenv("TECH_WORKS") == "true"
LOCALRUN = os.getenv("LOCALRUN") == "true"

if TECH_WORKS:
    @dp.message()
    @dp.callback_query()
    async def tech_works(message: Message, user: User):
        await message.answer(user.localize("tech_works"))
    
    logger.warning("TECH WORKS ENABLED")

# import handlers after dp initialization
from src.handlers.routes import *          # noqa: E402
from src.handlers.user import *            # noqa: E402
from src.handlers.query_keyboard import *  # noqa: E402
#from src.handlers.admin import *           # noqa: E402

import src.background as background          # noqa: E402

async def on_startup(bot: Bot):
    dp["bot"] = bot

    botname = (await bot.get_me()).username
    dp["botname"] = botname
    logger.success(f"Run as @{botname}")


    if LOCALRUN:
        logger.warning("LOCALRUN IS TRUE")
        logger.warning("LOCALRUN IS TRUE")
        logger.warning("LOCALRUN IS TRUE")
        

    # run background tasks
    asyncio.create_task(background.check_fizra(bot))
    #asyncio.create_task(backgroud.is_wallet_time_expired(bot))
    #asyncio.create_task(backgroud.export_to_sheets(bot))
    #asyncio.create_task(backgroud.check_fiat_top_ups(bot))
    #asyncio.create_task(backgroud.user_buy_now_notification(bot))

    if User.select().where(User.user_id == int(os.getenv("OWNER_ID"))).first() is None:
        logger.debug(f"User with id {os.getenv('OWNER_ID')} not found. Creating it as OWNER.")
        User.create(
            user_id = int(os.getenv("OWNER_ID")),
            role = UserRole.OWNER.value,
        )

    await bot.set_my_commands(main_commands)
    logger.success("User commands was set")

    # set admin commands
    admins: list[User] = User.select().where(User.role >= UserRole.ADMIN.value)
    admin_scope = [BotCommandScopeChat(chat_id = admin.user_id) for admin in admins]

    for scope in admin_scope:
        await bot.set_my_commands(main_commands + admin_commands, scope = scope)

    logger.success(f"Admin commands was set for {len(admins)} users")

    # get last edited file in /dumps
    # send to owner_id
    dumps_files = glob.glob('./dumps/*') # * means all if need specific format then *.csv

    if len(dumps_files) > 0:
        latest_file = max(dumps_files, key=os.path.getmtime)

        logger.info(f"Latest dump file: {latest_file}")
        try:
            await bot.send_document(
                chat_id = int(os.getenv("OWNER_ID")),
                document = FSInputFile(latest_file)
            )
        except Exception:
            logger.exception("Can't send dump file")