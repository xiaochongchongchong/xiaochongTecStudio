# xiaochongTecStudio

个人技术工作室 Monorepo，汇总各类学习与演示项目。

## 目录结构
```
xiaochongTecStudio/
├── rag/        # RAG 检索增强生成学习项目（方案 A 手写版 + 方案 B LangChain 版 + 多步 Agent）
├── fastapi/    # FastAPI 三步学习 Demo（从最小 API 到 JWT 鉴权）
└── ...
```

## 当前项目

### [fastapi/](fastapi/README.md) — FastAPI 三步学习 Demo
一套「边看原理边动手」的渐进式 FastAPI 练习，从最小 API 演进到模块化 + 真实 JWT 鉴权。

| 步骤 | 学什么 | 说明 |
| --- | --- | --- |
| Step 1 | 路由匹配、路径参数、自动文档、自动序列化 | [README.md](fastapi/README.md) |
| Step 2 | Pydantic 请求体校验、`Depends` 依赖注入、`Header()` | 同上 |
| Step 3 | `APIRouter` 模块化、`pydantic-settings` 读 `.env`、**JWT 鉴权** | 同上 |

**技术栈**：FastAPI + uvicorn + Pydantic + pydantic-settings + PyJWT。

### [rag/](rag/README.md) — RAG 学习项目
本地向量化 + 远程大模型的检索增强生成案例，含两套可运行方案：

| 方案 | 说明 | 文档 |
| --- | --- | --- |
| 方案 A | 手写实现，含企业级优化（智能切分、混合检索、Rerank、引用溯源） | [README.md](rag/README.md) |
| 方案 B | LangChain 标准框架重构 | [README_langchain.md](rag/README_langchain.md) |
| 多步 Agent | LangGraph 检索-评估-重试回路，自动纠偏 | [README_agent.md](rag/README_agent.md) |
| 代码详解 | 逐段讲解两方案每个函数/概念 | [DOCS_CODE.md](rag/DOCS_CODE.md) |
| 项目指南 | 背景/选型/环境搭建/复现/模型切换/优化方向 | [PROJECT_GUIDE.md](rag/PROJECT_GUIDE.md) |

**技术栈**：本地 embedding（bge-small-zh）+ 本地向量库（chromadb）+ 远程大模型（dsv4-flash，OpenAI 兼容接口）。

## 使用说明
- 各子目录为独立项目，含各自的说明文档。
- 涉及 API 密钥的配置均提供 `.env.example` 模板，真实密钥不入库。
- 运行前请参考对应子目录的 README 完成环境配置。
