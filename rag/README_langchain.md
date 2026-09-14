# RAG 学习案例 —— 方案 B（LangChain 版）

本方案用 **LangChain** 标准框架重构 RAG 链路，与方案 A（手写版）共享同一份 `.env` 配置和 `data/` 语料，但使用独立的向量库目录，互不干扰。

## 技术栈
- **框架**：LangChain（`langchain-core` / `langchain-openai` / `langchain-chroma` / `langchain-huggingface`）
- **切分**：`RecursiveCharacterTextSplitter`
- **Embedding（本地）**：`HuggingFaceEmbeddings`，模型 `BAAI/bge-small-zh-v1.5`
- **向量库（本地）**：`Chroma`（`chroma_langchain/` 目录）
- **生成模型（远程）**：`ChatOpenAI` 接 `dsv4-flash`（`https://llm-api.focus-on.pro/v1`）

## 目录结构
```
D:\ai\rag
├── src/rag_langchain/       # 方案 B：LangChain 版
│   ├── __init__.py
│   └── main.py              # build_chain() + main()
├── chroma_langchain/        # 方案 B 的向量库持久化
├── data/                    # 共享知识文档
└── .env                     # 共享配置
```

## LangChain 标准链路（main.py）
1. **加载文档** → `_load_documents()`：用 `Document` 读取 `data/` 下的 md/txt
2. **切分** → `RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)`
3. **向量化** → `HuggingFaceEmbeddings(model_name=EMBED_MODEL)`
4. **入库** → `Chroma.from_documents(...)`，持久化到 `chroma_langchain/`
5. **检索** → `vector_store.as_retriever(search_kwargs={"k": 4})`
6. **生成** → `RunnablePassthrough.assign(context=...)` → `PROMPT` → `ChatOpenAI` → `StrOutputParser`

## 如何运行
```powershell
cd D:\ai\rag
if not defined HF_ENDPOINT set HF_ENDPOINT=https://hf-mirror.com
set PYTHONPATH=D:\ai\rag\src
.\.venv\Scripts\python.exe -m rag_langchain.main
```
启动后输入问题即可问答，输入 `q` 退出。

## 与方案 A 的对比
| 维度 | 方案 A（手写） | 方案 B（LangChain） |
| --- | --- | --- |
| 代码 | 透明，每一步可见 | 框架封装，组件化 |
| 切分 | `split_text()` 自定义 | `RecursiveCharacterTextSplitter` |
| 检索 | 向量 + 关键词 + Rerank 重排 | 向量（默认），可叠加 |
| 引用溯源 | 附带 `[来源: xxx]` | 可自定义 |
| 学习价值 | 理解 RAG 底层 | 理解企业主流框架用法 |
| 扩展性 | 手动组合 | 组件丰富，易扩展 |

## 配置（.env，共享）
```
LLM_API_BASE=https://llm-api.focus-on.pro/v1
LLM_API_KEY=sk-rpFx9zxd0pqZ7Sh51zmfOA
LLM_MODEL=dsv4-flash
EMBED_MODEL=BAAI/bge-small-zh-v1.5
```

## 依赖（已在 .venv 安装）
`langchain-core`、`langchain-openai`、`langchain-chroma`、`langchain-huggingface`、`langchain-text-splitters`
