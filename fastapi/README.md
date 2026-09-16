# FastAPI 三步学习 Demo（从零到 JWT 鉴权）

> 一套「边看原理边动手」的渐进式 FastAPI 练习。从最简单的最小 API，一步步演进到模块化 + 真实 JWT 鉴权的标准后端结构。
>
> 技术栈：`FastAPI` + `uvicorn` + `Pydantic` + `pydantic-settings` + `PyJWT`

---

## 三步概览

| 步骤 | 文件夹 | 学什么 | 端口 |
| --- | --- | --- | --- |
| **Step 1** | `step1\` | 路由匹配、路径参数、自动文档、自动序列化 | 8001 |
| **Step 2** | `step2\` | Pydantic 请求体校验、`Depends` 依赖注入、`Header()` | 8002 |
| **Step 3** | `step3\` | `APIRouter` 模块化、`pydantic-settings` 读 `.env`、**JWT 鉴权** | 8003 |

## 演进逻辑

| | Step 1 | Step 2 | Step 3 |
| --- | --- | --- | --- |
| 核心主题 | 跑通最小 API | 请求校验 + 依赖注入 | 模块化 + 真实鉴权(JWT) |
| 文件数 | 1 个 `main.py` | 1 个 `main.py` | `app/` 多个模块 |
| 路由 | `@app.get` 直接写 | 同 step1 | `APIRouter` + `include_router` |
| 数据校验 | 只靠类型注解 | **Pydantic `BaseModel`** | 同 step2 |
| 鉴权 | 无 | 固定字符串 `=="secret"` | **JWT + PyJWT** |
| 配置 | 硬编码 | 硬编码 | **`pydantic-settings` 读 `.env`** |
| 登录接口 | 无 | 无 | **`POST /login` 签发 token** |

---

## 环境准备

```powershell
# 推荐用 uv 管理（或 pip）
cd fastapi
python -m venv .venv
.\.venv\Scripts\activate

# 安装依赖（step3 需要）
pip install fastapi "uvicorn[standard]" pydantic-settings PyJWT python-multipart
```

---

## 如何运行

### Step 1 —— 最小 API
```powershell
cd step1
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8001
```
浏览器打开 `http://localhost:8001/docs`

### Step 2 —— 请求校验 + 依赖注入
```powershell
cd step2
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8002
```
浏览器打开 `http://localhost:8002/docs`
> 鉴权方式：请求头 `Authorization: Bearer secret`（演示用固定字符串）

### Step 3 —— 模块化 + 真实 JWT 鉴权
```powershell
cd step3
# 先复制配置模板
cp .env.example .env        # 然后改 SECRET_KEY 等
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8003
```
浏览器打开 `http://localhost:8003/docs`

> **Step 3 登录账号**：用户名 `admin`，密码 `123456`（演示用假用户表）

---

## Step 3 的 JWT 鉴权流程

```
① POST /api/v1/login   提交 username/password  →  返回 access_token
② 在 Swagger 右上角点 Authorize，填 username/password → 自动换 token
③ 之后调用受保护接口(如 /api/v1/items) → 自动带 token → 通过
```

### 关键文件
| 文件 | 职责 |
| --- | --- |
| `app/config.py` | `pydantic-settings` 读 `.env` |
| `app/security.py` | JWT 签发(`create_access_token`) + 校验(`decode_token`) |
| `app/dependencies.py` | `get_current_user` 鉴权依赖 |
| `app/routers/login.py` | 登录接口，签发 token |
| `app/routers/items.py` | 业务接口（受保护） |
| `app/main.py` | FastAPI 入口 + `include_router(prefix="/api/v1")` |

---

## 目录结构

```
fastapi/
├── step1/
│   └── main.py              # 最小可用：app + 路由 + 类型注解
├── step2/
│   └── main.py              # 加校验(BaseModel) + 依赖注入(Depends/Header)
└── step3/
    ├── .env.example         # 配置模板（SECRET_KEY 等，真实密钥不入库）
    └── app/
        ├── main.py          # FastAPI + include_router(prefix="/api/v1")
        ├── config.py        # pydantic-settings 读 .env
        ├── security.py      # JWT：create_access_token(签发) + decode_token(校验)
        ├── dependencies.py  # get_current_user：JWT 校验 + 抛401
        ├── schemas.py       # Pydantic 模型
        ├── api/main.py      # 汇总所有 router
        └── routers/
            ├── items.py     # APIRouter(prefix="/items")
            └── login.py     # 登录接口，签发 token
```

## 说明
- `__init__.py` 为空文件，用于标记 Python 包。
- `.env` 不入库（已在 `.gitignore`），只提供 `.env.example` 模板。
- **安全提醒**：`SECRET_KEY` 务必改成一个随机强密码，别用默认值。
