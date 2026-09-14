# RAG 学习案例 —— 方案 A（手写，含企业级优化）

本仓库含两个可运行的 RAG 方案：
- **方案 A（本文件）**：手写实现，含企业级优化（智能切分、混合检索、Rerank、引用溯源）
- **方案 B**：[LangChain 版 → README_langchain.md](README_langchain.md)

这是一个**不依赖 LangChain**、可运行的本地化 RAG 案例，采用手写代码实现企业级检索增强生成链路。

## 技术栈
- **Embedding（本地）**：sentence-transformers，模型 `BAAI/bge-small-zh-v1.5`
- **Rerank 重排（本地）**：CrossEncoder，模型 `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **向量库（本地）**：chromadb（`chroma/` 目录持久化）
- **生成模型（远程/自建）**：`dsv4-flash`，OpenAI 兼容接口 `https://llm-api.focus-on.pro/v1`

## 企业级优化点
| 优化 | 实现 | 位置 |
| --- | --- | --- |
| 智能切分 | `split_text()` 按段落切分 + 控制 chunk 长度/重叠 | `main.py` |
| 向量检索 | `_vector_search()` 用 bge 转向量，chromadb 相似度检索 | `main.py` |
| 关键词补充 | `_keyword_relevance()` 中文/英文 token 命中率，辅助排序 | `main.py` |
| Rerank 重排 | `retrieve()` 用 CrossEncoder 对候选二次打分排序 | `main.py` |
| 引用溯源 | `answer()` 生成回答后附带 `[来源: xxx]` | `main.py` |

## RAG 完整链路（main.py）
1. **加载文档** → `load_documents()`：读取 `data/` 下的 md/txt
2. **智能切分** → `split_text()`：按段落切分，控制长度与重叠
3. **向量化** → `RAG._embed()`：bge 模型转向量
4. **入库** → `RAG.ingest()`：写入 chromadb
5. **检索** → `RAG.retrieve()`：向量检索 + 关键词辅助 + **Rerank 重排**
6. **生成** → `RAG.answer()`：检索片段 + 问题交给 dsv4-flash，附来源

## 目录结构
```
D:\ai\rag
├── data/               # 知识文档（md/txt），放这里
│   └── rag_intro.md    # 示例文档
├── src/rag/
│   ├── __init__.py
│   └── main.py         # RAG 类 + 企业级优化
├── chroma/             # 向量数据库持久化目录
├── .env                # API 配置
├── run.bat             # 一键启动脚本（含镜像与编码设置）
├── pyproject.toml
└── .venv/              # 虚拟环境
```

## 如何运行
直接双击 `D:\ai\rag\run.bat`，或：
```powershell
cd D:\ai\rag
if not defined HF_ENDPOINT set HF_ENDPOINT=https://hf-mirror.com
set PYTHONPATH=D:\ai\rag\src
.\.venv\Scripts\python.exe -m rag.main
```
启动后有示例知识库，输入问题即可问答，输入 `q` 退出。

## 配置（.env）
```
LLM_API_BASE=https://llm-api.focus-on.pro/v1
LLM_API_KEY=sk-rpFx9zxd0pqZ7Sh51zmfOA
LLM_MODEL=dsv4-flash
EMBED_MODEL=BAAI/bge-small-zh-v1.5
RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```

## 说明
- **模型下载**：embedding 与 rerank 模型首次运行需下载（走 hf-mirror 镜像），之后走本地缓存。
- **数据安全**：embedding、rerank、向量库均在本地；仅"生成"环节调用远程大模型。
- **rerank 模型语言**：当前用英文 `ms-marco` 模型，中文效果有限；若要中文可换 `BAAI/bge-reranker-base`（体积较大）。
- **控制台乱码**：Windows 默认编码导致，`run.bat` 已用 `chcp 65001` 解决。
