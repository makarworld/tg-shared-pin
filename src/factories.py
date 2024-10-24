from aiogram.filters.callback_data import CallbackData
from aiogram.filters.state import State, StatesGroup

class CallbackFactory(CallbackData, prefix = "kb"):
    action: str

class AskChangePinFactory(CallbackData, prefix = "acp"):
    action: str
    pin_id: int
    user_id: int

class MultiKeyboardFactory(CallbackData, prefix = "mk"):
    action: str # select | back
    page: int
    item_selected: int 
    kb_session: str

class StateFactory:
    class RedeemPromoState(StatesGroup):
        input_code: State = State()
