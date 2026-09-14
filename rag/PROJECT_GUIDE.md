# RAG 项目指南（背景 · 选型 · 搭建 · 复现 · 扩展）

本文档回答三个问题：**为什么这么选？怎么从零复现？后续怎么扩展？**
配套文档：`README.md`（方案 A）、`README_langchain.md`（方案 B）、`DOCS_CODE.md`（代码详解）。

---

## 1. 项目背景与目标

本项目是一个**可运行的 RAG 学习案例**，目标是复现企业级检索增强生成链路，同时保持代码清晰、能在一台普通笔记本上跑通。

设计取舍：
- **本地 embedding + 本地向量库**：数据不出本机，且不依赖付费云服务。
- **远程大模型生成**：因为你的笔记本无独显、内存仅约 16GB，本地跑 LLM 吃力，所以"生成"环节调用自建的 `dsv4-flash`（OpenAI 兼容接口）。
- **手写版 + LangChain 版双方案**：手写版理解 RAG 底层，LangChain 版学习企业主流框架用法。

## 2. 为什么这样选型

| 环节 | 选型 | 理由 |
| --- | --- | --- |
| 嵌入模型 | `BAAI/bge-small-zh-v1.5` | 轻量（约 100MB）、中文效果好、CPU 可跑 |
| 向量库 | Chroma | 纯 Python、无需 Docker、可持久化、适合学习 |
| 重排模型 | `cross-encoder/ms-marco-MiniLM-L-6-v2` | 轻量 cross-encoder，二次打分 |
| 生成模型 | `dsv4-flash`（远程接口） | 笔记本跑不动本地 LLM，改用远程接口 |
| 部署 | 无 Docker | 笔记本资源有限，避免重平台 |

**核心权衡**：把"重计算"（LLM）放远程，把"轻计算"（embedding/rerank/向量检索）放本地。这样既学了完整 RAG，又不卡机器。

## 3. 环境搭建与复现指南

### 3.1 前置条件
- Python 3.14+（本项目在 3.14 验证）
- `uv`（包管理）：`pipx install uv` 或 `uv` 官方安装
- 可访问 `hf-mirror.com`（国内无法直连 huggingface.co）

### 3.2 安装依赖
```powershell
cd D:\ai\rag
# 创建虚拟环境
uv venv
# 安装项目依赖
uv pip install chromadb sentence-transformers openai python-dotenv
# 方案 B 需要额外安装 LangChain 相关
uv pip install langchain-core langchain-openai langchain-chroma langchain-huggingface langchain-text-splitters
```

### 3.3 配置
创建 `.env`（参考 `.env.example`）：
```ini
LLM_API_BASE=https://llm-api.focus-on.pro/v1
LLM_API_KEY=your_api_key_here
LLM_MODEL=dsv4-flash
EMBED_MODEL=BAAI/bge-small-zh-v1.5
RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```

### 3.4 首次运行（需下载模型）
模型首次运行会从 `hf-mirror.com` 下载，之后走本地缓存（`~/.cache/huggingface`）。

```powershell
# 设置镜像（关键！否则下载会超时）
$env:HF_ENDPOINT = "https://hf-mirror.com"
$env:PYTHONPATH = "D:\ai\rag\src"

# 方案 A
.\.venv\Scripts\python.exe -m rag.main
# 方案 B
.\.venv\Scripts\python.exe -m rag_langchain.main
```

也可以直接双击 **`D:\ai\rag\run.bat`**（已内置镜像与编码设置）。

### 3.5 遇到的坑（已解决）
| 问题 | 原因 | 解决 |
| --- | --- | --- |
| 下载模型超时 | 国内无法直连 huggingface.co | 设 `HF_ENDPOINT=https://hf-mirror.com` |
| 中文乱码 | Windows 控制台默认编码 | `chcp 65001`（`run.bat` 已内置） |
| 依赖安装超时 | LangChain 依赖树较大 | 逐个包安装（`langchain-core` → `langchain-openai` → ...） |
| `relational` 被误忽略 | `.gitignore` 的 `.env.*` 规则 | 用 `!.env.example` 白名单保留模板 |

## 4. 如何切换模型

### 4.1 换生成模型（LLM）
改 `.env` 的 `LLM_MODEL` 和 `LLM_API_BASE` 即可（只要目标接口是 OpenAI 兼容）。
```ini
LLM_MODEL=qwen3.8-27b
LLM_API_BASE=https://llm-api.focus-on.pro/v1
```

### 4.2 换 embedding 模型
改 `.env` 的 `EMBED_MODEL`。注意：**换了 embedding 模型必须重建向量库**（不同模型向量维度/语义不同，旧向量无法复用）。
```ini
EMBED_MODEL=BAAI/bge-large-zh-v1.5
```
重建方式：删除 `chroma/` 或 `chroma_langchain/` 目录后重新运行入库。

### 4.3 换 rerank 模型
改 `.env` 的 `RERANK_MODEL`。中文场景可换 `BAAI/bge-reranker-base`（更准但更大，约 700MB）。
```ini
RERANK_MODEL=BAAI/bge-reranker-base
```

## 5. 数据安全与私有化

- **本地侧**（安全）：embedding、rerank、向量库均在本地，文档不出本机。
- **远程侧**（注意）：仅"生成"环节把**检索到的片段 + 问题**发给远程大模型。若文档敏感，需评估是否可接受，或改为本地 LLM。
- **密钥**：`LLM_API_KEY` 只在 `.env` 中，已通过 `.gitignore` 排除，不提交仓库。

## 6. 后续优化方向

| 方向 | 说明 |
| --- | --- |
| 中文重排 | 换 `BAAI/bge-reranker-base` |
| 真正混合检索 | 向量 + BM25/全文检索融合 |
| 更智能切分 | 语义切分、按标题层级切分 |
| 引用溯源增强 | 返回具体片段位置/页码 |
| 评测 | 用 RAGAS 等评估检索与生成质量 |
| 生产化 | 换 Milvus/Elasticsearch、加监控、多租户权限 |

## 7. 完整文档索引

- `README.md` — 方案 A（手写版）
- `README_langchain.md` — 方案 B（LangChain 版）
- `DOCS_CODE.md` — 代码逐段详解
- `PROJECT_GUIDE.md` — 本文件（背景/选型/搭建/扩展）
