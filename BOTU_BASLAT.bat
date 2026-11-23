@echo off
chcp 65001 >nul 2>&1
title TRADE ANALIZ - ANA BASLATICI
cd /d "%~dp0"

echo.
echo   ============================================
echo     TRADE ANALIZ PRO TERMINAL v3.2
echo   ============================================
echo.
echo   Baslatilacak servisler:
echo     1. Streamlit Web Paneli + Surekli Tarama Motoru (port 8503)
echo     2. FastAPI REST API (port 8502)
echo.
echo   ============================================
echo.

:: ── ÖNCEKİ İŞLEMLERİ TEMİZLE ──
echo   [0/2] Onceki Streamlit process'leri temizleniyor...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8503" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul 2>&1

:: ── STREAMLIT WEB PANELİ (tarama motoru bunun içinde daemon thread olarak başlar) ──
echo   [1/2] Streamlit web paneli + tarama motoru baslatiliyor...
start /B "" python -m streamlit run app.py --server.port 8503 --server.headless=true

echo   Streamlit hazir olana kadar bekleniyor (max 60 saniye)...

:: Streamlit'in hazir olmasini bekle
setlocal enabledelayedexpansion
set MAX_WAIT=60
set WAITED=0

:WAIT_LOOP
timeout /t 3 /nobreak >nul 2>&1
set /a WAITED=WAITED+3

powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8503/_stcore/health' -TimeoutSec 2 -UseBasicParsing; if ($r.Content -eq 'ok') { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1

if %errorlevel% equ 0 (
    echo   [OK] Streamlit hazir ^(%WAITED% saniye^)
    goto :OPEN_BROWSER
)

if %WAITED% lss %MAX_WAIT% goto :WAIT_LOOP

echo   [UYARI] Streamlit %MAX_WAIT% saniyede hazir olamadi, sayfa yine de aciliyor...
endlocal

:OPEN_BROWSER
echo   Web tarayici aciliyor...
start http://localhost:8503

:: ── FASTAPI REST API ──
echo   [2/2] FastAPI REST API baslatiliyor...
start /B "" python -m uvicorn api:app --host 0.0.0.0 --port 8502

echo.
echo   ============================================
echo     TUM SERVISLER BASLATILDI!
echo   ============================================
echo     Web Panel : http://localhost:8503
echo     API Doks  : http://localhost:8502/docs
echo     API       : http://localhost:8502
echo   ============================================
echo.
echo   NOT: Tarama motoru, web paneli acilinca arka planda
echo   otomatik baslar. Bu pencereyi kapatmayin.
echo.

pause