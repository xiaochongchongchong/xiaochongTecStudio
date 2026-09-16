# Step 1 · 最小可运行
# 原理点：路由匹配、路径参数类型转换、自动序列化、自动文档

from fastapi import FastAPI

app = FastAPI(title="Step 1 最小示例")


@app.get("/health")
async def health():
    """练习1：最简单的一个 GET 接口"""
    return {"status": "ok"}


@app.get("/items/{item_id}")
async def read_item(item_id: int):
    """练习2：路径参数 + 类型转换（item_id:int，传非数字会 422）"""
    return {"item_id": item_id}
