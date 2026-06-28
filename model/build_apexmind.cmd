@echo off
REM Build (or rebuild) your own `apexmind` model from the Modelfile.
REM Requires Ollama installed and the base model in the Modelfile already pulled
REM (default base: llama3.1  ->  ollama pull llama3.1).
cd /d "%~dp0\.."
echo Building apexmind from model\ApexMind.Modelfile ...
ollama create apexmind -f model\ApexMind.Modelfile
echo.
echo Done. Test it:   ollama run apexmind "what is your name and who made you?"
echo It also appears in the ApexMind chat model dropdown.
