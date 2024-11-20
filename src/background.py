
from aiogram import Bot
from typing import *
import asyncio
import os

from src.models import *
from src.utils import get_last_fizra_posts

async def check_fizra(bot: Bot):
    logger.info("Start check_fizra")

    FZ_CHANNEL_ID = int(os.getenv("FZ_CHANNEL_ID"))

    while True:
        try:
            last_posts = get_last_fizra_posts()

            items = last_posts["response"]["items"]

            last_post: FizraPost = FizraPost.select().order_by(FizraPost.vk_id.desc()).first()
            if last_post:
                last_fizra_post_id = last_post.vk_id
            else:
                last_fizra_post_id = 1017

            for item in items:
                # check if post already exists
                exist_post: FizraPost = FizraPost.select().where(FizraPost.vk_id == item["id"]).first()

                if exist_post:
                    current_hash = hashlib.sha256(item["text"].encode('utf-8')).hexdigest()
                    if exist_post.text_hash != current_hash:
                        exist_post.text_hash = current_hash
                        exist_post.save()

                        # edit text
                        await bot.edit_message_text(
                            text = localizator('fizra_post', 'ru', post_id = last_fizra_post_id, text = text),
                            chat_id = FZ_CHANNEL_ID,
                            message_id = exist_post.tg_id
                        )
                        logger.success(f"[check_fizra] Post was updated: {exist_post}")


                if item["id"] > last_fizra_post_id:
                    last_fizra_post_id = item["id"]
                    text = item["text"]
                    
                    m = await bot.send_message(FZ_CHANNEL_ID, localizator('fizra_post', 'ru', post_id = last_fizra_post_id, text = text))

                    fp = FizraPost(vk_id = last_fizra_post_id, 
                                tg_id = m.message_id, 
                                text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest())
                    fp.save()
                    logger.success(f"[check_fizra] New post: {fp}")
                    
                    await asyncio.sleep(5)
            
            logger.info(f"[check_fizra] was checked: {last_fizra_post_id}")

            await asyncio.sleep(60 * 1) # 1 min

        except Exception as e:  
            logger.error(e)
            await asyncio.sleep(60 * 1)