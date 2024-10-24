from __future__ import annotations
import copy
import math
from typing import *
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData
from peewee import ModelSelect


from src.models import BaseModel, User, BookType
from src.factories import CallbackFactory, MultiKeyboardFactory
from src.utils import load_yaml, KeyboardStorage, keyboard_session, add_session_to_keyboard, logger

class keyboard:
    config_file = "./src/keyboards.yml"
    keyboards = load_yaml(config_file)
        
    @staticmethod
    def _get_config(key: str, update: bool = False) -> Dict[dict]:
        """Get config from keyboard.yml file"""
        if update:
            keyboard.keyboards = load_yaml(keyboard.config_file)

        return copy.deepcopy(keyboard.keyboards.get(key))

    @staticmethod
    def _build_keyboard(config: List[List[dict]], 
                        localize: Callable[[str], str],
                        data_factory: CallbackData = CallbackFactory,
                        factory_kwargs: dict = {},
                        **formats: dict) -> InlineKeyboardMarkup:
        """Build keyboard from config"""
        # Init builder
        builder = InlineKeyboardBuilder()

        # Add all buttons from config
        for button in config["buttons"]:
            # Add button
            if button.get("url"):
                # type url button
                button_kwargs = {
                    "url": button["url"].format(**formats)
                }
            elif button.get("data"):
                # type callback_data button
                if isinstance(button["data"], dict):
                    button_kwargs = {
                        "callback_data": data_factory(
                            # Add formats to all values in dict button.data
                            **{k: v.format(**formats) for k, v in button["data"].items()}, 
                            # Add extra kwargs
                            **factory_kwargs
                        ).pack()
                    }
                else:
                    button_kwargs = {
                        "callback_data": button["data"].format(**formats)
                    }
            text_kwargs = button.get('formats', {})
            text_kwargs.update(formats)

            builder.button(
                # Set text
                text = localize(button["locale"], **text_kwargs) if button["locale"].startswith("direct:") is False else button["locale"][7:], 
                # Add kwargs
                **button_kwargs
            )

        # Set adjust        
        builder.adjust(*config["adjust"])

        # Return as InlineKeyboardMarkup
        return builder.as_markup()

    @staticmethod
    def create(kb_route: str, localize: Callable[[str], str], part_session: str = None, **formats) -> InlineKeyboardMarkup:
        """Get config from keyboard.yml file and return builded keyboard"""
        config = keyboard._get_config(kb_route, update = True)
        if config is None:
            logger.error(f"Keyboard {kb_route} not found")
            return None
        
        if part_session is not None:
            config = add_session_to_keyboard(config, part_session)

        return keyboard._build_keyboard(config, localize, **formats)
# 
# This code was transfered and rewrited from @MultiCode_Robot (author: @abuztrade)
#
    
    @staticmethod
    def book(user: User,
             query: ModelSelect, 
             localize: Callable[[str], str],
             select_handler: Callable,
             default_text: str = "Default text is not set",
             page: int = 1, 
             remove_footer: bool = False,
             btn_format: str = "[{user_id}] {first_name}",
             book_type: str = BookType.ONE.value, # ONE | MANY
             back_callback: str = CallbackFactory(action = "main_menu").pack(),
             item_format: Callable = lambda btn_format, item: btn_format.format(**item.__data__),
             width: int = 2, 
             height: int = 6, **kwgs) -> InlineKeyboardMarkup:
        """
        Построение кнопок должно быть универсальным не зависимо от того какое в них содержимое
        Нижняя часть всегда остаётся одной и той же
        Можно взять handler который будет вызываться при выборе кнопки
        Или сделать это check клавиатурой где первый символ заменяется на галку если кнопка была нажата
        Все данные можно хранить в стейте
        Функция должна понимать откуда брать данные для перелистывания

        Для каких ситуаций нужна клавиатура:
         1. [БД] Отобразить всех пользователей для создания комнаты + те что выбраны должны переместиться на первую страницу
                 - Тут будет единый стиль кнопок который можно сделать через format
         2. [БД] Отобразить все заявки на модерацию
                 - Здесь в названии должен быть номер заявки
         3. [БД] Отображение кодеров/клиентов в комнате
                 - same #1
         4. [БД] Выбрать стеки для рассылки
                 - будет просто нейм стека
         5. [БД] Отобразить вообще всех пользователей
                 - same #1

        Итого: 
         Проще всего брать готовый query и оттуда вытягивать данные по номеру страницы
         ? как сохранить select_handler и передать его в обработчик. Это должно быть сохранено в state!
         ! тогда придётся сделать метод асинхронным и передавать стейт 

        """
        #await MultiKeyboard.active.set()
        KeyboardStorage.setdefault(user.user_id, {})

        data: dict = KeyboardStorage.get(user.user_id)
        if not data.get('kb_session') or data.get(query) != query:
            kb_session = keyboard_session()
            KeyboardStorage[user.user_id].update(
                user = user,
                db = query.model,
                query = query,
                select_handler = select_handler,
                default_text = default_text,
                book_type = book_type,
                btn_format = btn_format,
                back_callback = back_callback,
                width = width,
                height = height,
                kb_session = kb_session
            )
        else:
            kb_session = data.get('kb_session')

        if book_type == BookType.MANY.value:
            selected = data.get('selected', [])
            selected_at_current_page = selected[(page - 1) * height * width: page * height * width]

        # Нужно чтобы то что было выбрано прыгало на первую страницу если это BookType.MANY.value
            
        if book_type == BookType.MANY.value:
            selected_items = query.model.select().where(query.model.id.in_(selected)).offset((page - 1) * height * width)\
                            .limit(width * height)
            
            empty_items = width * height - selected_items.count()

            if empty_items == 0:
                # page full
                page_content = list(selected_items)
            else:
                page_content = (list(selected_items) +
                                list(query()\
                                .where(query.model.id.not_in(selected))
                                .offset((page - 1) * height * width - len(selected))
                                .limit(empty_items)))

        else:
            page_content = query.offset((page - 1) * height * width).limit(width * height)

        page_content: List[BaseModel]

        all_count: int = query.count()
        kb = {
            "buttons": [],
            "adjust": []
        }

        # add 2 buttons per row
        kb["adjust"] += [width] * (len(page_content) // width) 

        # if not enough items for filling page
        if f := page_content.count() % width:
            kb["adjust"] += [f]

        # add footer
        if remove_footer is False:
            kb["adjust"] += [3, 1]


        for row in page_content:
            text = item_format(btn_format, row)

            if book_type == BookType.MANY.value:
                if row.id in selected_at_current_page:
                    text = localize("buttons.ok_emoji") + text
                
            kb["buttons"].append({
                "locale": f"direct:{text}",
                "data": MultiKeyboardFactory(action = "select", page = page, item_selected = row.id, kb_session = kb_session).pack()
            })
        
        # Добавить нижнюю часть для переключения страниц и выхода
        # + Кнопка отправить если это BookType.MANY

        # footer 
        # [<<] [0/0] [>>]
        # [     Menu    ]
        if remove_footer is False:
            max_page = math.ceil(all_count / (height * width))

            kb["buttons"] += [{
                "locale": "direct:<<",
                "data": MultiKeyboardFactory(action = "page", page = page - 1, item_selected = 0, kb_session = kb_session).pack()
            }, {
                "locale": f"direct:{page}/{max_page}",
                "data": MultiKeyboardFactory(action = "secret", page = page, item_selected = 0, kb_session = kb_session).pack()
            }, {
                "locale": "direct:>>",
                "data": MultiKeyboardFactory(action = "page", page = page+1, item_selected = 0, kb_session = kb_session).pack()
            }]

        kb["buttons"] += [{
            "locale": "buttons.back",
            "data": back_callback
        }]

        if remove_footer is False:
            if book_type == BookType.MANY.value:
                kb["buttons"].append({
                    "locale": "buttons.send",
                    "data": MultiKeyboardFactory(action = "send", page = page, item_selected = 0, kb_session = kb_session).pack()
                })
        return keyboard._build_keyboard(kb, localize)
