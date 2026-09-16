# FastAPI 原理详解（入门到深入）

> 写给「懂 Python、但没接触过 Web 框架或框架底层的人」。
> 目标：读完能真正**理解** FastAPI 是怎么工作的，而不是只背结论。

---

## 目录
1. [先搞懂：Web 服务到底在干嘛](#一先搞懂web-服务到底在干嘛)
2. [FastAPI 的"三层"到底指什么](#二fastapi-的"三层"到底指什么)
3. [一碗面的比喻：谁来煮，谁来端](#三一碗面的比喻谁来煮谁来端)
4. [核心魔法一：类型注解驱动一切](#四核心魔法一类型注解驱动一切)
5. [核心魔法二：一个请求进来后发生了什么](#五核心魔法二一个请求进来后发生了什么)
6. [核心魔法三：async 和事件循环](#六核心魔法三async-和事件循环)
7. [核心魔法四：依赖注入 Depends](#七核心魔法四依赖注入-depends)
8. [核心魔法五：自动文档是怎么来的](#八核心魔法五自动文档是怎么来的)
9. [最小可运行示例（可自己跑）](#九最小可运行示例可自己跑)
10. [常见误区 / 反模式](#十常见误区--反模式)
11. [一页速查表](#十一一页速查表)

---

## 一、先搞懂：Web 服务到底在干嘛

在讲 FastAPI 之前，先想清楚：**任何 Web 后端都只做 4 件事**。

```
客户端(浏览器/手机)  ──发请求──▶  服务器(你的代码)  ──返回响应──▶  客户端
                       HTTP 请求                        HTTP 响应
```

一次请求包含 3 大类信息，服务器要处理它们：

| 请求里有什么 | 例子 | 后端要做什么 |
| --- | --- | --- |
| **路径 + 方法** | `GET /items/123` | 决定"该调用哪个函数" |
| **参数** | `/items/123` 里的 `123`；`?page=2` | 把数据传给函数 |
| **请求体** | `{"name": "苹果", "price": 5}` | 解析 + 校验成 Python 对象 |

服务器做完整流程就是：**接收到请求 → 找到对应函数 → 拿数据给它 → 它返回结果 → 转成响应发回去**。

FastAPI 的目标：**把这 4 步里的脏活累活全自动搞定，你只管写业务函数。**

---

## 二、FastAPI 的"三层"到底指什么

很多人说"FastAPI = Starlette + Pydantic"，但没讲清各管什么。用一张图拆开：

```
┌─────────────────────────────────────────────────────────┐
│ ①  FastAPI  ——  薄薄的"翻译层"                            │
│     作用：读你的类型注解，告诉下面两层该怎么干              │
│     它自己不处理 HTTP，也不处理校验，只做"指挥"             │
├─────────────────────────────────────────────────────────┤
│ ②  Starlette  ——  "餐厅经理"                              │
│     作用：路由匹配(哪桌客人)、中间件(迎宾/结账)、           │
│           WebSocket、生命周期                               │
│     它是实际干 HTTP 活的框架                               │
├─────────────────────────────────────────────────────────┤
│ ③  ASGI  ——  "行业标准"，一个接口约定                       │
│     作用：定义 Web 应用长什么样：                          │
│           async def app(scope, receive, send)             │
│     它是底层协议，Starlette 严格照它实现                    │
└─────────────────────────────────────────────────────────┘
```

**关键区分：**
- **FastAPI（应用层）**：你 import 的是它，`FastAPI()` 创建 app。它负责"业务怎么组织"。
- **Starlette（框架层）**：FastAPI 内部**依赖**它。路由、中间件这些能力其实是 Starlette 给的。
- **ASGI（协议层）**：一套规定"Web 应用接口长什么样"的标准。Starlette 实现了 ASGI，所以能用 uvicorn 跑。

> 打个比方：**ASGI 是"国家电力标准"**（所有人都得遵守），**Starlette 是"发电厂"**（实际发电），**FastAPI 是"你家电器"**（好用，但电来自发电厂）。

---

## 三、一碗面的比喻：谁来煮，谁来端

这个比喻能彻底理清 `uvicorn` 和 `FastAPI` 的分工。

```
你点单(发请求)
   │
   ▼
【服务员 = uvicorn】   ←—— ASGI 服务器
   站在门口，接待所有客人(请求)，把单子传给后厨
   客人在等(网络 I/O)，他不闲着，继续接别的客人
   │
   ▼
【后厨 = 你的 FastAPI 应用】
   接到单子(请求)，按菜谱(路由)找到对应厨师(你的函数)
   厨师做菜(跑业务逻辑)，做好就叫服务员端出去
   │
   ▼
【端菜 = uvicorn】
   把做好的菜(响应)端回给客人
```

- **uvicorn** 是**服务器**：负责底层 socket、监听端口、接收/发送请求。它不认识你的业务。
- **FastAPI** 是**应用**：负责"收到请求后怎么处理"。它自己不监听端口。

> 这就是为什么启动命令是 `uvicorn main:app` —— 意思是「用 uvicorn 这个服务器，去跑 `main.py` 里那个叫 `app` 的 FastAPI 应用」。**app 是被服务的对象，uvicorn 是服务者。**

---

## 四、核心魔法一：类型注解驱动一切

这是 FastAPI 最独特、也最容易被低估的地方。先看普通写法 vs FastAPI 写法。

### 普通 Flask/手写 Web 框架（要自己写解析校验）

```python
# 伪代码：Flask 风格
@app.post("/items")
def create_item():
    body = request.get_json()            # 1. 手动解析 body
    name = body.get("name")              # 2. 手动取字段
    if not isinstance(name, str):        # 3. 手动校验类型
        return error("name 必须是字符串", 422)
    price = body.get("price")
    if not isinstance(price, float):     # 4. 手动校验
        return error("price 必须是数字", 422)
    # ... 全部手动，而且没文档，ides 也没提示
```

### FastAPI 写法（只用类型注解）

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Item(BaseModel):      # ① 定义数据结构
    name: str
    price: float

@app.post("/items")         # ② 声明路由
async def create_item(item: Item) -> Item:   # ③ 用类型注解声明"要什么"
    return item             # ④ 直接返回 Python 对象
```

**FastAPI 从类型注解里读到了什么，并自动帮你做了什么：**

| 你写的类型注解 | FastAPI 自动做的事 |
| --- | --- |
| `item: Item`（请求体参数） | 自动解析 JSON body → 校验 → 转成 `Item` 对象；缺字段/类型错 → 自动返回 **422** 错误 |
| `-> Item` 或 `response_model=Item` | 把返回的 Python 对象自动**序列化成 JSON** |
| `item_id: int`（路径参数） | 自动解析路径里的 `123` 转成整数；非数字 → 422 |
| `page: int = 1`（查询参数） | 自动读 `?page=2` 并转成 int |
| （整套类型信息） | 自动生成 **OpenAPI 文档**（/docs）和 IDE 补全 |

**就一句话：你不写任何校验/序列化代码，只写类型标注，框架全能替你搞定。**

这就是为什么 FastAPI 文档好、代码少、类型安全 —— **它的核心思路是"类型即契约"**。

### 再了解 Pydantic 在干嘛

`Item` 继承自 `pydantic.BaseModel`，这个类本身就很"智能"：

```python
class Item(BaseModel):
    name: str
    price: float

item = Item(name="苹果", price=5)     # 正常
item = Item(name="苹果")               # 报错：price 缺失
item = Item(name="苹果", price="五")   # 报错：price 不是数字
```

Pydantic 负责：**类型校验、数据转换、序列化、JSON Schema 生成**。FastAPI 借用它做请求/响应的数据校验层。

---

## 五、核心魔法二：一个请求进来后发生了什么

上面讲了"该干什么"，这里讲"实际顺序"。一次请求的完整流程：

```
客户端发送：POST /items   body={"name":"苹果","price":5}
   │
   ▼
① uvicorn 收到请求，把它包成 3 样东西：
     scope = {method:"POST", path:"/items", ...}      # 请求元信息
     receive()  → 能读到请求体                        # 异步读 body
     send()     → 能发响应                            # 异步发响应
   │
   ▼
② uvicorn 调用你的 app：  await app(scope, receive, send)
   │
   ▼
③ FastAPI 让 Starlette 做【路由匹配】
     根据 method=POST, path=/items 找到对应的函数 create_item
   │
   ▼
④ FastAPI 做【依赖解析】
     看 create_item 函数签名，发现需要 item: Item
     于是调用 Depends(如果有) 解析依赖（本例无，直接下一步）
   │
   ▼
⑤ FastAPI 做【参数解析 + Pydantic 校验】
     item: Item → 用 receive() 读 body → Item.model_validate(body)
     校验通过 → 得到 Item 对象；失败 → 自动返回 422
   │
   ▼
⑥ 执行你的业务函数  create_item(item)
     返回 Item 对象（Python 对象，还没转 JSON）
   │
   ▼
⑦ FastAPI 做【响应序列化】
     根据 -> Item / response_model，把返回对象校验+转成 JSON
   │
   ▼
⑧ 通过 send() 把 JSON 响应发回给 uvicorn
   │
   ▼
业务返回客户端
```

**记住：顺序是「路由匹配 → 依赖解析 → 参数校验 → 执行 → 序列化 → 返回」。**
理解了这个顺序，很多 bug 就好定位了（比如"为什么我参数没校验就报错了？"）。

---

## 六、核心魔法三：async 和事件循环

这是 FastAPI 高性能的核心，也是最容易踩坑的地方。

### 先理解"事件循环"是什么

一个屋子只有**一个服务员（一个线程/事件循环）**，但有**很多客人**。

- **同步（阻塞）**：服务员给 1 号客人点完单，就**站在那等**他吃完，第 2 号客人只能干等。→ 串行，慢。
- **异步（非阻塞）**：服务员给 1 号客人下单后，**转身就去服务 2 号**，等 1 号的菜好了再回来端。→ 一人服务多人，快。

在代码里：
- 一个 `async def` 函数，遇到 `await`（等待，比如读数据库、调外部 API）就**主动让出**，去处理别的请求。
- 等那个 I/O 完成了，再回来继续。

```python
import asyncio

async def handle():
    print("开始")
    await asyncio.sleep(2)     # 让出 2 秒，这 2 秒去服务别人
    print("完成")
```

**这就是 FastAPI 快的秘密**：一个事件循环，靠 `await` 频繁让出，同时处理成百上千个请求。它**不需要很多线程**。

### 三种路由写法，性能天差地别

| 写法 | 例子 | 性能/风险 |
| --- | --- | --- |
| `async def` + `await 非阻塞I/O` | `await asyncio.sleep()` / `await db.fetch()` | ✅ 最理想，事件循环不卡 |
| `def`（同步） | `def get(): time.sleep(1)` | ⚠️ 能工作，FastAPI 丢进**线程池**（默认40线程），不卡事件循环，但占线程资源 |
| `async def` + `time.sleep()` | `async def get(): time.sleep(1)` | ❌ **灾难**，阻塞整个事件循环，所有请求都卡住 |

**为什么第三种是灾难？** 因为 `async def` 里出现 `time.sleep`（同步阻塞）,它不会 `await`，事件循环没法让出，**整进程卡 1 秒**,期间所有其他请求都排队。这就是 `fastapi-best-practices` 里 `terrible-ping` 的例子。

### 什么时候用 async，什么时候用 def（结论）

| 你的代码做的是 | 建议 |
| --- | --- |
| 等数据库、等外部 API（非阻塞 I/O） | `async def` + `await` |
| 同步库（没有异步版本，如 `requests`） | `def`（走线程池）或 `await run_in_threadpool(...)` |
| **CPU 密集**（大量计算/视频转码） | 线程没用（GIL），改用 Celery 等独立进程 |

> **GIL 是什么**：Python 默认同一时刻只有一个线程能执行字节码。所以 CPU 密集任务开线程也没用，得开**进程**。

---

## 七、核心魔法四：依赖注入 Depends

### 普通写法 vs 依赖注入

设想多个接口都要"从数据库拿当前用户"，普通写法每处都重复：

```python
# 没有依赖注入：每个接口都重复"取用户"逻辑
@app.get("/profile")
def profile(token):
    user = auth_get_user(token)      # 每次都要写
    if not user:
        raise 401
    return user

@app.get("/orders")
def orders(token):
    user = auth_get_user(token)      # 又写一遍
    if not user:
        raise 401
    return user
```

### 用 Depends 之后

```python
from typing import Annotated
from fastapi import Depends

def get_current_user(token: str):
    user = auth_get_user(token)
    if not user:
        raise HTTPException(401)
    return user

CurrentUser = Annotated[dict, Depends(get_current_user)]

@app.get("/profile")
def profile(user: CurrentUser):       # 自动注入，不用自己写
    return user

@app.get("/orders")
def orders(user: CurrentUser):        # 同样自动注入
    return user
```

**Depends 做了两件事：**
1. **按函数签名自动解析**：你声明 `user: Depends(get_current_user)`，FastAPI 就自动调用 `get_current_user`，把返回值塞进 `user`。
2. **按请求缓存（只执行一次）**：如果同一请求里 `get_current_user` 被依赖 3 次，FastAPI 只真正调用 **1 次**，结果复用。

### 依赖还能"链式"

一个依赖可以依赖另一个依赖，自动帮你串联校验逻辑：

```python
def valid_post_id(post_id: UUID4):       # 校验帖子存在
    post = get_by_id(post_id)
    if not post:
        raise 404
    return post

def parse_jwt(token: str):               # 校验登录
    return decode_jwt(token)

def valid_owned_post(
    post = Depends(valid_post_id),       # ① 先校验帖子存在
    token = Depends(parse_jwt),          # ② 再校验登录
):
    if post["owner"] != token["user"]:   # ③ 再校验归属
        raise 403
    return post
```

### 为什么这是"最佳实践"重点

- 把「从数据库查并校验」「登录鉴权」拆成独立依赖，**多处复用，避免重复代码**。
- 测试时用 `app.dependency_overrides[xxx] = fake` **轻松替换依赖**（比如把真实数据库换成假的），不用 mock 整个内部。这是 `fastapi-best-practices` 反复强调的。

---

## 八、核心魔法五：自动文档是怎么来的

为什么 FastAPI 能免费给你 `/docs`？因为它**在启动时扫描了你所有的路由**，把每个接口的信息收集成一份 **OpenAPI** 规范（`openapi.json`）。

对你写的：
```python
@app.get("/items/{item_id}", response_model=Item)
async def read_item(item_id: int):
    ...
```

FastAPI 会生成这样的一段 OpenAPI JSON：
```json
{
  "/items/{item_id}": {
    "get": {
      "parameters": [{"name": "item_id", "in": "path", "schema": {"type": "integer"}}],
      "responses": {"200": {"content": {"application/json": {"schema": {...}}}}}
    }
  }
}
```

然后：
- `/docs` → 用 **Swagger UI** 渲染这份 JSON，可以**直接在网页上试接口**。
- `/redoc` → 用 **ReDoc** 渲染成静态文档页。

**所以：你类型标注写得越全，文档越完整，还不用维护两份。**

---

## 九、最小可运行示例（可自己跑）

把下面存成 `D:\ai\fastAPI\myapp\main.py`，跑起来就能看到原理生效。

```python
# main.py
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel

app = FastAPI(title="FastAPI 原理演示")

# 一个简单的"依赖"
def get_current_user(token: str):
    if token != "secret":
        raise HTTPException(401, "未登录")
    return {"id": 1, "name": "张三"}

CurrentUser = Annotated[dict, Depends(get_current_user)]

# 数据模型
class Item(BaseModel):
    name: str
    price: float

@app.get("/health")
async def health():
    """健康检查 - async 路由"""
    return {"status": "ok"}

@app.post("/items", response_model=Item)
async def create_item(item: Item, user: CurrentUser):
    """创建商品 - 演示 body 解析 + 依赖注入 + 响应序列化"""
    print(f"用户 {user['name']} 创建了 {item}")
    return item

@app.get("/items/{item_id}")
def read_item(item_id: int, user: CurrentUser):
    """读取商品 - 演示路径参数转 int + 同步 def 路由"""
    return {"item_id": item_id}
```

运行：
```powershell
cd D:\ai\fastAPI\myapp
pip install fastapi uvicorn
uvicorn main:app --reload
```

打开浏览器：
- `http://localhost:8000/docs` → 自动生成的 Swagger 文档（点开试接口）
- `http://localhost:8000/openapi.json` → 机器可读的接口规范
- `http://localhost:8000/health` → 直接看返回

---

## 十、常见误区 / 反模式

这是 `fastapi-best-practices` 的 `AGENTS.md` 专门列给 AI 的错误清单，也是初学者最常犯的：

| 误区 | 为什么错 | 正确做法 |
| --- | --- | --- |
| `async def` 里用 `time.sleep` / `requests.get` | 阻塞事件循环，所有请求卡死 | 用 `await asyncio.sleep` / `httpx.AsyncClient`，或 `def` 路由 |
| 用 `python-jose` 做 JWT | 库已不维护 | 用 `PyJWT`（`import jwt`） |
| `from jose import jwt` 等 | 同上 | `import jwt` |
| `Field(ge=18, default=None)` | 约束和默认值矛盾 | 要么必填 `Field(ge=18)`，要么可选 `int | None = None` |
| `def get_user(id: int = Depends(...))` | 旧写法有默认值坑 | `user: Annotated[User, Depends(...)]` |
| 路由里 `except Exception` 吞掉所有错误 | 把真实 bug 变成静默 200 | 捕获具体异常，抛 `HTTPException` |
| `BackgroundTasks` 放重要任务 | 无重试，worker 挂了任务就丢 | 重要任务用 Celery/Arq/RQ |
| async 路由里用同步 ORM Session | 阻塞事件循环/死锁连接池 | 用异步 `AsyncSession` |
| 返回对象还用 `response_model` 同款 | 对象被构造两次 | 要么返回 dict 让 `response_model` 校验，要么去掉 `response_model` |

---

## 十一、一页速查表

| 概念 | 一句话解释（现在应该能看懂了） |
| --- | --- |
| **ASGI** | 规定"Web 应用接口长什么样"的异步标准，`async def app(scope, receive, send)` |
| **Starlette** | 真正干 HTTP 活的框架（路由、中间件），FastAPI 的"底座" |
| **Pydantic** | 负责数据校验 + 序列化，是 FastAPI 类型安全与文档的来源 |
| **FastAPI** | 薄薄一层，读你的类型注解，指挥 Starlette + Pydantic 干活 |
| **类型注解** | 你写 `x: int` 或 `body: Item`，框架就自动校验/解析/生成文档 |
| **uvicorn** | ASGI 服务器，负责监听端口、收/发请求，把请求喂给 app |
| **事件循环** | 单线程靠 `await` 频繁让出，同时处理海量请求，这就是高性能来源 |
| **线程池** | 同步 `def` 路由被 FastAPI 丢进这里（默认40线程），避免卡事件循环 |
| **Depends** | 依赖注入：按函数签名自动解析 + 同请求只执行一次 |
| **response_model** | 自动校验并序列化返回值 |
| **OpenAPI** | 自动生成的接口规范，`/docs`、`/redoc` 都靠它 |
```
