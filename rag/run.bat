@echo off
chcp 65001 >nul
if not defined HF_ENDPOINT set HF_ENDPOINT=https://hf-mirror.com
set PYTHONPATH=D:\ai\rag\src
cd /d D:\ai\rag
.venv\Scripts\python.exe -m rag.main
