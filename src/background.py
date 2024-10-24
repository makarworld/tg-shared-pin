
from datetime import datetime, timedelta
from aiogram.types import FSInputFile
from functools import partial
from aiogram import Bot
from typing import *
import asyncio
import os

from src.models import *
from src.keyboards import keyboard
from src.utils import get_last_fizra_posts

async def check_fizra(bot: Bot):
    logger.info("Start check_fizra")

    while True:
        last_posts = get_last_fizra_posts()

        items = last_posts["response"]["items"]

        if os.path.exists('last_fizra_post_id.temp'):
            with open('last_fizra_post_id.temp', 'r') as f:
                last_fizra_post_id = int(f.read())
        else:
            with open('last_fizra_post_id.temp', 'w') as f:
                f.write('1017')
            last_fizra_post_id = 1017
        
        for item in items:
            if item["id"] > last_fizra_post_id:
                last_fizra_post_id = item["id"]
                text = item["text"]
                
                FZ_CHANNEL_ID = int(os.getenv("FZ_CHANNEL_ID"))

                await bot.send_message(FZ_CHANNEL_ID, localizator('fizra_post', 'ru', post_id = last_fizra_post_id, text = text))

                with open('last_fizra_post_id.temp', 'w') as f:
                    f.write(str(last_fizra_post_id))
                
                await asyncio.sleep(5)
        
        logger.info(f"[check_fizra] was checked: {last_fizra_post_id}")

        await asyncio.sleep(60 * 30) # 30 min
