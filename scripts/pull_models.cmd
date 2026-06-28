@echo off
REM Pull 10 good free local models for ApexMind (via Ollama).
REM Run after installing Ollama:  scripts\pull_models.cmd
REM Big models need more RAM; comment out any your machine can't handle.

echo === Best free CODE model ===
ollama pull qwen2.5-coder:7b

echo === Lighter coder (low RAM) ===
ollama pull qwen2.5-coder:3b

echo === Strong general models ===
ollama pull qwen2.5:7b
ollama pull llama3.1
ollama pull mistral:7b
ollama pull gemma2:9b

echo === Fast / lightweight ===
ollama pull llama3.2:3b
ollama pull phi3.5

echo === Reasoning + math ===
ollama pull deepseek-r1:8b

echo === Bigger coder (needs ~16GB RAM / GPU) ===
ollama pull deepseek-coder-v2:16b

echo Done. They will appear in the Chat model dropdown automatically.
