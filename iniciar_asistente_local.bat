@echo off
title Servidor RAG Local - Qwen 2.5 7B & DeepSeek-R1
echo ============================================================
echo   Iniciando Servidor RAG Local para el Asistente IA
echo   Modelos habilitados: Qwen 2.5 7B y DeepSeek-R1 (Ollama)
echo ============================================================
cd /d "%~dp0"
"C:\Users\elias\.gemini\antigravity\scratch\open-webui-env\Scripts\python.exe" local_rag_server.py
pause
