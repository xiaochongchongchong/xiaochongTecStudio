# Step 2 · Pydantic + 依赖注入
# 原理点：请求体校验、Depends 注入、HTTPException

from typing import Annotated
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Step 2 校验 + 依赖注入")

# 一个"依赖"：校验 token 是否合法（用 Header() 读取 HTTP 的 Authorization 头）
def get_current_user(authorization: Annotated[str, Header()] = "Bearer secret"):
    # 简化演示：Authorization 形如 "Bearer secret"
    token = authorization.removeprefix("Bearer ").strip()
    if token != "secret":
        raise HTTPException(status_code=401, detail="未登录或 token 无效")
    return {"id": 1, "name": "张三"}


# 用 Annotated 把它变成一个"可注入类型"
CurrentUser = Annotated[dict, Depends(get_current_user)]


# Pydantic 请求体模型
class Item(BaseModel):
    name: str
    price: float


@app.post("/items", response_model=Item)
async def create_item(item: Item, user: CurrentUser):
    """演示：请求体校验 + 依赖注入 + 响应序列化"""
    print(f"用户 {user['name']} 创建了 {item}")
    return item


@app.get("/items/{item_id}")
def read_item(item_id: int, user: CurrentUser):
    """演示：路径参数 + 同步 def 路由（走线程池）"""
    return {"item_id": item_id, "creator": user["name"]}
