from __future__ import annotations

import os
from pathlib import Path
from typing import TypedDict

import shutil

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, StateGraph

load_dotenv()

LLM_API_BASE = os.getenv("LLM_API_BASE", "https://llm-api.focus-on.pro/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "dsv4-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-zh-v1.5")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma_langchain"


class AgentState(TypedDict):
    question: str
    attempts: int
    context: list[str]
    answer: str
    notes: str


def _load_documents(data_dir: Path) -> list[Document]:
    docs = []
    for path in sorted(data_dir.glob("*.md")) + sorted(data_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        docs.append(Document(page_content=text, metadata={"source": path.name}))
    return docs


def build_retriever():
    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    chunks = splitter.split_documents(_load_documents(DATA_DIR))
    # 每次重建前清空旧的 Chroma 库，避免重复往同一目录追加导致数据堆积
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR),
    )
    return vector_store.as_retriever(search_kwargs={"k": 6})


def make_agent():
    retriever = build_retriever()
    llm = ChatOpenAI(base_url=LLM_API_BASE, api_key=LLM_API_KEY, model=LLM_MODEL)

    def _dedup(texts: list[str]) -> list[str]:
        # 按内容去重：去掉重复/高度相似的片段
        seen: set[str] = set()
        out: list[str] = []
        for t in texts:
            t = t.strip()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out

    def retrieve(state: AgentState) -> AgentState:
        docs = retriever.invoke(state["question"])
        texts = _dedup([d.page_content for d in docs])  # 解决重复片段问题
        state["context"] = texts
        return state

    def rewrite_query(state: AgentState) -> AgentState:
        # 问题2：用 LLM 将完整问句改写为"关键词式"检索查询。
        # 关键发现：bge-small-zh 对完整问句的向量语义会偏向句法/语气词，
        # 反而不如关键词能精准命中实体与术语。这里把问句提炼成空格分隔的关键词串。
        prompt = (
            "请把下面这个问题改写成最适合在知识库中做相似度检索的中文查询。"
            "要求：只输出改写后的查询，不要任何解释；"
            "把问题中的核心概念、实体、术语提取成关键词，用空格分隔，"
            "去掉'是什么''为什么'等提问词和语气词，尽量精炼。\n\n"
            f"问题：{state['question']}"
        )
        resp = llm.invoke(prompt)
        new_q = (resp.content or "").strip()
        if new_q:
            state["question"] = new_q
        state["attempts"] = state.get("attempts", 0) + 1
        return state

    def assess(state: AgentState) -> AgentState:
        # 问题1：用 LLM 判断检索内容是否真正相关
        if not state["context"]:
            state["notes"] = "未检索到任何内容"
            return state
        joined = "\n".join(state["context"])[:1500]
        prompt = (
            "请判断下面检索到的上下文是否与这个问题相关。"
            "如果上下文完全没有回答该问题的信息，回复 0；如果相关，回复 1。只回复 0 或 1。\n\n"
            f"问题：{state['question']}\n\n上下文：\n{joined}"
        )
        resp = llm.invoke(prompt)
        judge = (resp.content or "").strip()
        if judge.startswith("0"):
            state["notes"] = "检索内容与问题不相关"
            state["attempts"] = state.get("attempts", 0) + 1
        else:
            state["notes"] = "检索内容相关"
        return state

    def generate(state: AgentState) -> AgentState:
        context = "\n\n".join(state["context"]) or "（未检索到相关上下文）"
        prompt = (
            "你是一个企业知识库助手。请仅基于以下上下文回答用户问题，"
            "如上下文不足请明确说明，不要编造。\n\n"
            f"【上下文】\n{context}\n\n"
            f"【问题】\n{state['question']}\n\n"
            "【回答】"
        )
        resp = llm.invoke(prompt)
        state["answer"] = resp.content or ""
        return state

    def route(state: AgentState) -> str:
        # 条件边：检索不佳且未重试过 -> 改写查询重试；否则生成
        if state.get("attempts", 0) < 2 and state.get("notes", "").startswith("未检索到") or (
            state.get("attempts", 0) < 2 and state.get("notes", "") == "检索内容与问题不相关"
        ):
            return "retry"
        return "generate"

    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("assess", assess)
    graph.add_node("rewrite", rewrite_query)
    graph.add_node("generate", generate)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "assess")
    graph.add_conditional_edges(
        "assess",
        route,
        {"retry": "rewrite", "generate": "generate"},
    )
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("generate", END)

    return graph.compile()


def main() -> None:
    agent = make_agent()
    print("多步 Agent 已就绪。输入问题，输入 q 退出。")
    while True:
        q = input("\n问题: ")
        if q.strip().lower() in {"q", "quit", "exit"}:
            break
        result = agent.invoke({"question": q, "attempts": 0, "context": [], "answer": "", "notes": ""})
        print(result["answer"])


if __name__ == "__main__":
    main()
