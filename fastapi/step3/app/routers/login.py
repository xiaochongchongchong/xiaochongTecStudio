from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.security import create_access_token

router = APIRouter(tags=["login"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# 简化的"用户表"：演示用，真实项目应查数据库
FAKE_USERS = {"admin": {"password": "123456", "id": "1"}}


@router.post("/login", response_model=TokenResponse)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """登录：接受 Swagger Authorize 弹窗填写的 username/password 表单"""
    user = FAKE_USERS.get(form.username)
    if not user or user["password"] != form.password:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user["id"])
    return TokenResponse(access_token=token)
