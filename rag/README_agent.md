# 多步 Agent（LangGraph 版）—— 让 RAG 学会"自己判断检索够不够好"

> 这是在方案 B（LangChain）基础上，用 **LangGraph** 把"检索 → 判断 → 生成"从一条直线
> 升级成**可循环、可重试、可自动纠偏**的多步 Agent。它让系统在"检索不准"时能自己发现并修正，
> 而不是把错误上下文硬喂给大模型。

## 为什么需要多步 Agent

传统 RAG（方案 A / B）是一条固定的单向流水线：

```
问题 ──► 向量检索 ──► 拼上下文 ──► 大模型生成
```

问题在于：**如果检索到的内容不相关，后面全错。** 系统不会察觉，只会拿错误上下文生成答案，
导致幻觉或答非所问。多步 Agent 引入"**评估反馈回路**"：

```
问题 ──► 检索 ──► 评估相关性 ──► 相关？──► 生成
                                  ▲│
                             不相关 ┘ (改写查询重试, 最多 N 次)
```

关键能力：
- **评估（assess）**：让大模型判断检索结果与问题是否相关，而不是无脑生成。
- **重试（rewrite）**：不相关时，把查询改写成更适合检索的形式，再检索一轮。
- **循环控制**：最多重试 N 次，避免死循环；耗尽后仍生成，但会说明上下文不足。
- **去重（dedup）**：检索可能返回重复/高度相似片段，先合并再交给模型，避免重复信息干扰。

## 结构（graph 节点与边）

| 节点 | 作用 |
| --- | --- |
| `retrieve` | 检索 + 去重，写入 `context` |
| `assess` | 用 LLM 判断 `context` 是否相关，写入 `notes` |
| `rewrite_query` | 把问题改写为"关键词式"查询，`attempts + 1` |
| `generate` | 基于 `context` 生成最终答案 |

```
set_entry_point → retrieve → assess ─(条件路由)─→ rewrite → retrieve (循环)
                                    └──────────→ generate → END
```

`route` 条件边：若 `attempts < 2` 且检索不相关 → 去 `rewrite` 重试；否则去 `generate`。

```python
def route(state):
    if state["attempts"] < 2 and state["notes"] in ("未检索到任何内容", "检索内容与问题不相关"):
        return "retry"
    return "generate"
```

## 运行

```powershell
cd D:\ai\rag
if not defined HF_ENDPOINT set HF_ENDPOINT=https://hf-mirror.com
set PYTHONPATH=D:\ai\rag\src
.\.venv\Scripts\python.exe -m rag_langchain.agent
```

`agent.py` 里的 `main()` 提供交互式命令行，`make_agent()` 返回编译好的 LangGraph 图。

## 这次调优踩到的 3 个真实"检索坑"

调试过程中，Agent 一开始对"RAG 的典型流程是什么？"反复重试仍答不出。排查后发现
是**检索系统本身**的问题，而不是 Agent 逻辑，逐个修复：

### 坑 1：向量库被重复追加，数据越堆越多
`Chroma.from_documents` 每次运行都往同一个 `chroma_langchain/` 目录**追加**，
不会覆盖。多次调试后库里有 24 条数据，但实际文档只有 3 个 chunk，剩下全是重复墙，干扰检索。

**修复**：重建前先 `shutil.rmtree(CHROMA_DIR)` 清空，保证每次都是干净的库。

```python
if CHROMA_DIR.exists():
    shutil.rmtree(CHROMA_DIR)
```

### 坑 2：完整问句的向量语义会"跑偏"
对比测试发现，用 `bge-small-zh` 做嵌入时：

| 查询 | 检索命中 |
| --- | --- |
| `RAG 的典型流程是什么？`（完整问句） | ❌ 命中"为什么需要 RAG" |
| `典型流程`（关键词） | ✅ 命中"典型流程" |
| `RAG 文档导入 文本切分 向量化 检索`（关键词串） | ✅ 命中"典型流程" |

中文嵌入模型对**完整问句**（带"是什么""为什么"等提问词和语气）的语义会被句法主导，
反而不如**精炼的关键词**能精准对齐实体和术语。这就是完整问句检索不准的原因。

**修复**：`rewrite_query` 不再简单改写成另一种问法，而是**提取关键词式查询**。

```python
prompt = (
    "把问题改写成最适合在知识库做相似度检索的中文查询。只输出改写结果；"
    "提取核心概念/实体/术语为关键词，用空格分隔；去掉'是什么''为什么'等提问词。"
)
```

#### 修复前后对比（同一个问题）

| | 之前（改写为问句） | 之后（改写为关键词） |
| --- | --- | --- |
| attempts | 3（反复重试仍失败） | **0（一次命中）** |
| 检索片段 | 1（不相关） | **3（含"典型流程"）** |
| 回答 | "无法回答" | **完整列出 6 步** |

### 坑 3：检索会返回重复/高度相似的片段
`k=6` 时可能取到内容几乎相同的 chunk，直接拼给模型浪费上下文、稀释重点。

**修复**：`retrieve` 里用 `_dedup` 按内容去重。

## 相关文件
- `src/rag_langchain/agent.py`：多步 Agent 实现（`make_agent()`、`main()`）
- `src/rag_langchain/main.py`：方案 B 的单步基线
