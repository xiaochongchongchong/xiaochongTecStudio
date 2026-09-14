# RAG 代码详解（方案 A + 方案 B）

本文档面向学习，逐段讲解两个方案的代码。建议配合 `README.md`（方案 A）和 `README_langchain.md`（方案 B）一起看。

---

## 0. RAG 整体流程回顾

无论哪个方案，RAG 的核心都是 6 步：

```
文档 → 切分(Chunk) → 嵌入(Embedding/向量化) → 存向量库 → 检索(Retrieval) → 生成(Generation)
```

- **切分**：把长文档分成短片段，便于精准检索。
- **嵌入**：把每个文本片段转成一个向量（一串数字），语义相近的文本向量也相近。
- **向量库**：存向量，支持"找最相似"的查询。
- **检索**：把用户问题也转成向量，在向量库里找最相似的 N 个片段。
- **生成**：把检索到的片段和问题一起交给大模型，生成回答。

---

## 1. 方案 A（手写版）逐段讲解

文件：`src/rag/main.py`

### 1.1 配置读取（第 1-24 行）

```python
load_dotenv()                # 读取 .env 文件，把变量注入环境
LLM_API_BASE = os.getenv(...)  # 大模型接口地址
LLM_API_KEY  = os.getenv(...)  # API token
LLM_MODEL    = os.getenv(...)  # 生成模型名
EMBED_MODEL  = os.getenv(...)  # 嵌入模型名
RERANK_MODEL = os.getenv(...)  # 重排模型名
```

- `os.getenv(key, default)`：读取环境变量，取不到就用默认值。
- `Path(__file__).resolve().parent.parent.parent`：得到项目根目录（`src/rag/main.py` 往上三层），用来定位 `data/`。

### 1.2 智能切分 `split_text`（第 27-45 行）

```python
def split_text(text, chunk_size=300, overlap=50):
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    ...
```

- `re.split(r"\n\s*\n", text)`：按**空行**把文本切成段落。
- 逐个段落累积到 `buf`，超过 `chunk_size`（约 300 字）就切出一个片段。
- 优点：按段落切，保证片段语义完整，比固定长度硬切更合理。
- 说明：`overlap`（重叠）本意是让相邻片段有交集、避免上下文被切断，但当前实现只做了简化处理，未真正生成重叠。

### 1.3 类 `RAG`（第 48 行起）

**`__init__`（第 49-54 行）**：初始化四个核心对象
- `self.embedder = SentenceTransformer(EMBED_MODEL)`：本地嵌入模型（负责文本→向量）
- `self.reranker = CrossEncoder(RERANK_MODEL)`：本地重排模型（负责二次打分）
- `self.llm = OpenAI(base_url=..., api_key=...)`：大模型客户端（OpenAI 兼容）
- `self.collection = chromadb.PersistentClient().get_or_create_collection(...)`：向量库集合

**`_embed`（第 56-57 行）**：把一批文本转成向量
```python
return self.embedder.encode(texts).tolist()
```
- `encode(texts)` 返回 batch 向量，`.tolist()` 转成 Python 列表（chromadb 需要）。

**`ingest`（第 59-71 行）**：文档入库
```python
for doc, source in documents:
    for c in split_text(doc):        # 每个文档切成多个片段
        texts.append(c)
        metas.append({"source": source})   # 记录来源文件
vectors = self._embed(texts)
self.collection.upsert(ids, documents=texts, embeddings=vectors, metadatas=metas)
```
- 把每篇文档切成片段，批量向量化，写入向量库。
- `metadatas` 记录每个片段来自哪个文件（用于引用溯源）。

**`_vector_search`（第 73-82 行）**：纯向量检索
```python
qvec = self._embed([query])[0]        # 问题向量化
res = self.collection.query(query_embeddings=[qvec], n_results=top_k, include=[...])
```
- 用问题的向量在库里找最相似的 `top_k` 个片段，返回文本和元数据。

**`_keyword_relevance`（第 84-90 行）**：关键词命中率
```python
q_tokens = set(re.findall(r"[\u4e00-\u9fa5]{2,}|[a-zA-Z]{2,}", query.lower()))
```
- 用正则提取问题里的中文词（≥2 字）和英文词。
- 计算这些词有多少出现在片段里，作为**辅助相关性分数**（补充向量检索，缓解漏检）。

**`retrieve`（第 92-103 行）**：混合检索 + 重排（核心）
```python
candidates = self._vector_search(query, top_k=10)   # 1. 向量初检，多取一点(10)
scores = self.reranker.predict([(query, c["text"]) for c in candidates])  # 2. 重排打分
ranked.sort(key=lambda x: (x["score"], x["kw"]), reverse=True)  # 3. 按分数排序
return ranked[:top_k]   # 4. 取前 top_k
```
- 先用向量检索粗筛 10 个候选，再用 `CrossEncoder` 对"问题+片段"逐对打分精排，最后结合关键词分数，取前 4。
- 这就是**混合检索（向量 + 关键词）+ Rerank 重排**的企业级做法，能显著提升准确率。

**`answer`（第 105-123 行）**：生成回答 + 引用溯源
```python
context = "\n\n".join(h["text"] for h in hits)     # 拼检索到的片段
sources = "、".join(sorted({h["meta"].get("source", "") for h in hits ...}))  # 收集来源
prompt = f"【上下文】\n{context}\n\n【问题】\n{query}\n\n【回答】"
resp = self.llm.chat.completions.create(model=LLM_MODEL, messages=[{"role":"user","content":prompt}])
return f"{ans}\n\n[来源: {sources}]"   # 回答末尾附上来源文件
```
- 构造提示词：**上下文 + 问题**一起给大模型，并强调"只基于上下文、不要编造"。
- 返回时自动在末尾附上 `[来源: xxx.md]`，实现引用溯源。

### 1.4 加载文档 `load_documents`（第 126-132 行）

```python
for path in sorted(data_dir.glob("*.md")):   # 读 md 文件
    docs.append((path.read_text(encoding="utf-8"), path.name))
for path in sorted(data_dir.glob("*.txt")):  # 读 txt 文件
    ...
```
- 读 `data/` 下的 md/txt，返回 `(文本, 文件名)` 列表。

### 1.5 入口 `main`（第 135-151 行）

```python
rag = RAG()                 # 初始化
rag.ingest(load_documents(DATA_DIR))   # 加载并入库
while True:                 # 交互问答
    q = input("问题: ")
    print(rag.answer(q))    # 检索 + 生成
```

---

## 2. 方案 B（LangChain 版）逐段讲解

文件：`src/rag_langchain/main.py`

### 2.1 依赖与配置（第 1-24 行）

LangChain 的组件按包划分：
- `langchain_chroma` → 向量库 Chroma
- `langchain_core.runnables` → 链式组合 `RunnablePassthrough`
- `langchain_huggingface` → 本地嵌入 `HuggingFaceEmbeddings`
- `langchain_openai` → 大模型 `ChatOpenAI`
- `langchain_text_splitters` → 切分 `RecursiveCharacterTextSplitter`

配置读取和方案 A 相同（复用 `.env`）。

### 2.2 Prompt 模板（第 26-31 行）

```python
PROMPT = PromptTemplate.from_template(
    "你是一个企业知识库助手...【上下文】\n{context}\n\n【问题】\n{question}\n\n【回答】"
)
```
- `{context}` 和 `{question}` 是占位符，运行时由链自动填充。

### 2.3 加载文档 `_load_documents`（第 34-41 行）

```python
from langchain_core.documents import Document
docs.append(Document(page_content=text, metadata={"source": path.name}))
```
- 把每个文件包装成 LangChain 的 `Document` 对象（含 `page_content` 和 `metadata`）。

### 2.4 构建链 `build_chain`（第 44-71 行）—— 核心

```python
embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)   # 嵌入模型
splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)  # 切分器
chunks = splitter.split_documents(docs)   # 自动切分 Document 列表

vector_store = Chroma.from_documents(     # 向量化并入库
    documents=chunks, embedding=embeddings, persist_directory=str(CHROMA_DIR))
retriever = vector_store.as_retriever(search_kwargs={"k": 4})  # 检索器

llm = ChatOpenAI(base_url=..., api_key=..., model=...)  # 大模型

return (
    RunnablePassthrough.assign(context=lambda x: _format(retriever.invoke(x["question"])))
    | PROMPT
    | llm
    | StrOutputParser()
)
```

关键点：
- **`RecursiveCharacterTextSplitter`**：递归尝试按不同分隔符切分（换行、句号、空格等），比手写更智能，`chunk_overlap` 会真正生成重叠。
- **`Chroma.from_documents`**：一行完成"切分后向量化 + 存库 + 持久化"。
- **`as_retriever(k=4)`**：把向量库包装成检索器，取最相似 4 条。
- **`RunnablePassthrough.assign(context=...)`**：先自动调用 `retriever` 检索，把结果格式化后作为 `context` 传给下一步。
- **`|` 管道符**：把"检索→填模板→调模型→解析输出"串成一条链（LangChain 的 `Runnable` 语法，类似 Unix 管道）。
- **`StrOutputParser()`**：把模型返回的对象转成纯字符串。

### 2.5 入口 `main`（第 74-84 行）

```python
chain = build_chain()            # 构建整条链
chain.invoke({"question": q})    # 传入问题，自动走完检索→生成
```

---

## 3. 两方案核心概念对照

| 概念 | 方案 A（手写） | 方案 B（LangChain） |
| --- | --- | --- |
| 切分 | `split_text()` | `RecursiveCharacterTextSplitter` |
| 嵌入 | `SentenceTransformer.encode` | `HuggingFaceEmbeddings` |
| 向量库 | `chromadb.PersistentClient` | `Chroma.from_documents` |
| 检索 | 手写 `_vector_search` | `retriever.invoke` |
| 重排 | `CrossEncoder.predict` | 需额外叠加（默认无） |
| 生成 | `OpenAI.chat.completions` | `ChatOpenAI` + `| llm` |
| 组合 | 显式函数调用 | `RunnablePassthrough | ...` 管道 |

---

## 4. 关键知识点

- **Embedding / 向量化**：把文本映射成高维向量，语义越近向量越近。`bge-small-zh-v1.5` 是开源中文嵌入模型。
- **向量数据库**：存储并检索相似向量。Chroma 是轻量、纯 Python、可持久化的选择。
- **Chunk 切分**：片段太短→语义不全；太长→检索不准。`chunk_size` 与 `chunk_overlap` 是核心调参。
- **Rerank / 重排**：先粗筛（向量）再精排（cross-encoder），是提升准确率的关键技巧。
- **引用溯源**：把 `metadata` 里的来源随回答返回，便于审计与可信度。
- **混合检索**：向量检索 + 关键词检索结合，兼顾语义与精确匹配。

## 5. 常见问题

- **模型下载慢/失败**：设置 `HF_ENDPOINT=https://hf-mirror.com` 用国内镜像。
- **中文乱码**：Windows 控制台编码问题，`run.bat` 已用 `chcp 65001` 处理。
- **rerank 中文效果一般**：当前用英文 `ms-marco` 模型，可换成 `BAAI/bge-reranker-base`（更大、中文更佳）。
- **片段重复/重叠**：A 方案 `split_text` 的重叠是简化实现；B 方案 `RecursiveCharacterTextSplitter` 支持真正的 `chunk_overlap`。
