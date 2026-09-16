from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError

from app.security import decode_token

# 修正 tokenUrl 指向真实登录路径，Authorize 弹窗才能自动换 token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> dict:
    try:
        payload = decode_token(token)          # ① 验证签名 + 过期
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")               # ② 从 token 载荷取用户
    if not user_id:
        raise HTTPException(status_code=401, detail="token 缺少用户信息")
    # ③ 真实项目这里会查数据库确认用户仍有效，演示直接返回
    return {"id": user_id, "name": "张三"}


CurrentUser = Annotated[dict, Depends(get_current_user)]
