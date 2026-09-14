from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

LLM_API_BASE = os.getenv("LLM_API_BASE", "https://llm-api.focus-on.pro/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "dsv4-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-zh-v1.5")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma_langchain"

PROMPT = PromptTemplate.from_template(
    "你是一个企业知识库助手。请仅基于以下上下文回答用户问题，如上下文不足请明确说明，不要编造。\n\n"
    "【上下文】\n{context}\n\n"
    "【问题】\n{question}\n\n"
    "【回答】"
)


def _load_documents(data_dir: Path) -> list:
    from langchain_core.documents import Document

    docs = []
    for path in sorted(data_dir.glob("*.md")) + sorted(data_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        docs.append(Document(page_content=text, metadata={"source": path.name}))
    return docs


def build_chain():
    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    docs = _load_documents(DATA_DIR)
    chunks = splitter.split_documents(docs)

    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR),
    )
    retriever = vector_store.as_retriever(search_kwargs={"k": 4})

    llm = ChatOpenAI(
        base_url=LLM_API_BASE,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
    )

    def _format(docs) -> str:
        return "\n\n".join(d.page_content for d in docs)

    return (
        RunnablePassthrough.assign(context=lambda x: _format(retriever.invoke(x["question"])))
        | PROMPT
        | llm
        | StrOutputParser()
    )


def main() -> None:
    chain = build_chain()
    print("LangChain RAG 已就绪。输入问题，输入 q 退出。")
    while True:
        q = input("\n问题: ")
        if q.strip().lower() in {"q", "quit", "exit"}:
            break
        try:
            print(chain.invoke({"question": q}))
        except Exception as e:
            print(f"出错: {e}")


if __name__ == "__main__":
    main()
