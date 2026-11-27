@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PATH=%PATH%;%LocalAppData%\Programs\Ollama"

echo Ollama ve qwen2.5-coder:7b modeli hazirlaniyor...
ollama pull qwen2.5-coder:7b

echo.
echo Hazir! Pencereyi kapatmak icin herhangi bir tusa basin.
pause >nul
