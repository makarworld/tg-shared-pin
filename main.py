from aiogram import Bot
from aiogram.types import LinkPreviewOptions
from aiogram.client.default import DefaultBotProperties 
import dotenv 
import i18n
import os 

# append .env to environment
env = dotenv.dotenv_values(".env")

for key, value in env.items():
    os.environ[key] = value

DEBUG = os.getenv("DEBUG") == "true"

from src.handlers import dp, on_startup  # noqa: E402
from src import *                        # noqa: E402

# load locales
i18n.load_path.append(os.path.join(os.path.dirname(__file__), "locales"))
i18n.set("encoding", "utf-8")

if __name__ == "__main__":
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    # create bot instance
    bot = Bot(token = BOT_TOKEN, 
              default = DefaultBotProperties(
                  parse_mode = "HTML",
                  link_preview = LinkPreviewOptions(
                      is_disabled = True,
                      url = None,
                      prefer_small_media = False,
                      prefer_large_media = False,
                      show_above_text = False,
                   )))
    
    # add on_startup function
    async def wrapped_on_startup(*args, **kwargs):
        await on_startup(bot)
        
    dp.startup.register(wrapped_on_startup)
    # run
    dp.run_polling(bot)
