from fastapi import FastAPI

from app.api.main import api_router
from app.config import settings

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# 把子路由挂到主 app，统一前缀 /api/v1
app.include_router(api_router, prefix="/api/v1")
