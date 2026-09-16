from fastapi import APIRouter

from app.routers import items, login

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(items.router)
