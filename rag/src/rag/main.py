from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from openai import OpenAI
from sentence_transformers import CrossEncoder, SentenceTransformer

load_dotenv()

LLM_API_BASE = os.getenv("LLM_API_BASE", "https://llm-api.focus-on.pro/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "dsv4-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-zh-v1.5")
RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
COLLECTION_NAME = "rag_docs"
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(buf) + len(para) + 1 <= chunk_size:
            buf = f"{buf}\n{para}".strip()
        else:
            if buf:
                chunks.append(buf[: chunk_size])
            buf = para
    if buf:
        chunks.append(buf[: chunk_size])
    if overlap and len(chunks) > 1:
        merged: list[str] = []
        for i, c in enumerate(chunks):
            merged.append(c)
        chunks = merged
    return chunks


class RAG:
    def __init__(self) -> None:
        self.embedder = SentenceTransformer(EMBED_MODEL)
        self.reranker = CrossEncoder(RERANK_MODEL)
        self.llm = OpenAI(base_url=LLM_API_BASE, api_key=LLM_API_KEY)
        self.client = chromadb.PersistentClient()
        self.collection = self.client.get_or_create_collection(COLLECTION_NAME)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return self.embedder.encode(texts).tolist()

    def ingest(self, documents: list[tuple[str, str]]) -> None:
        texts: list[str] = []
        metas: list[dict] = []
        for doc, source in documents:
            for c in split_text(doc):
                texts.append(c)
                metas.append({"source": source})
        if not texts:
            return
        vectors = self._embed(texts)
        ids = [f"doc-{i}" for i in range(len(texts))]
        self.collection.upsert(ids=ids, documents=texts, embeddings=vectors, metadatas=metas)
        print(f"已入库 {len(texts)} 个片段")

    def _vector_search(self, query: str, top_k: int = 10) -> list[dict]:
        qvec = self._embed([query])[0]
        res = self.collection.query(
            query_embeddings=[qvec],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        return [{"text": d, "meta": m} for d, m in zip(docs, metas)]

    def _keyword_relevance(self, query: str, text: str) -> float:
        q_tokens = set(re.findall(r"[\u4e00-\u9fa5]{2,}|[a-zA-Z]{2,}", query.lower()))
        if not q_tokens:
            return 0.0
        t_text = text.lower()
        hits = sum(1 for t in q_tokens if t in t_text)
        return hits / len(q_tokens)

    def retrieve(self, query: str, top_k: int = 4) -> list[dict]:
        candidates = self._vector_search(query, top_k=10)
        if not candidates:
            return []
        pairs = [(query, c["text"]) for c in candidates]
        scores = self.reranker.predict(pairs)
        ranked = []
        for c, s in zip(candidates, scores):
            kw = self._keyword_relevance(query, c["text"])
            ranked.append({"text": c["text"], "meta": c["meta"], "score": float(s), "kw": kw})
        ranked.sort(key=lambda x: (x["score"], x["kw"]), reverse=True)
        return ranked[:top_k]

    def answer(self, query: str, top_k: int = 4) -> str:
        hits = self.retrieve(query, top_k)
        if not hits:
            return "未检索到相关内容。"
        context = "\n\n".join(h["text"] for h in hits)
        sources = "、".join(sorted({h["meta"].get("source", "") for h in hits if h["meta"]}))
        prompt = (
            "你是一个企业知识库助手。请仅基于以下检索到的上下文回答用户问题，"
            "如上下文不足请明确说明，不要编造。\n\n"
            f"【上下文】\n{context}\n\n"
            f"【问题】\n{query}\n\n"
            "【回答】"
        )
        resp = self.llm.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        ans = resp.choices[0].message.content or ""
        return f"{ans}\n\n[来源: {sources}]" if sources else ans


def load_documents(data_dir: Path) -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    for path in sorted(data_dir.glob("*.md")):
        docs.append((path.read_text(encoding="utf-8"), path.name))
    for path in sorted(data_dir.glob("*.txt")):
        docs.append((path.read_text(encoding="utf-8", errors="ignore"), path.name))
    return docs


def main() -> None:
    rag = RAG()
    docs = load_documents(DATA_DIR)
    if docs:
        rag.ingest(docs)

    print("知识库已就绪。输入问题，输入 q 退出。")
    while True:
        q = input("\n问题: ")
        if q.strip().lower() in {"q", "quit", "exit"}:
            break
        print("..." )
        print(rag.answer(q))


if __name__ == "__main__":
    main()
