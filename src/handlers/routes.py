from aiogram import Router

from src.handlers import dp

gif_router = Router(name = "gif")
admin_router = Router(name = "admin")
user_router = Router(name = "user")

# Dispatcher -> Router(admin) -> Router(user)
dp.include_router(admin_router)
#admin_router.include_router(gif_router)
admin_router.include_router(user_router)
