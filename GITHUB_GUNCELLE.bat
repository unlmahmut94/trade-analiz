@echo off
chcp 65001 >nul 2>&1
title TRADE ANALIZ - GITHUB OTOMATIK GUNCELLEYICI
cd /d "%~dp0"

echo.
echo ==================================================
echo      GITHUB KOD GUNCELLEME ISLEMI BASLATILDI
echo ==================================================
echo.

:: Degisiklik olup olmadigini kontrol et
git status --porcelain >nul 2>&1
for /f %%i in ('git status --porcelain') do set HAS_CHANGES=1

if not defined HAS_CHANGES (
    echo [BILGI] Guncellenecek yeni bir degisiklik bulunamadi.
    echo Kodlariniz zaten GitHub ile ayni!
    echo.
    pause
    exit /b
)

echo [1/3] Degisen ve yeni eklenen dosyalar hazirlaniyor...
git add .

echo [2/3] Degisiklikler tarih ve saat bilgisiyle paketleniyor...
git commit -m "Otomatik guncelleme: %date% %time:~0,5%"

echo [3/3] GitHub'a gonderiliyor (Push)...
git push

echo.
if %errorlevel% equ 0 (
    echo ==================================================
    echo   [BASARILI] Tum kodlar GitHub'a yuklendi!
    echo ==================================================
) else (
    echo ==================================================
    echo   [HATA] Yukleme sirasinda bir sorun olustu.
    echo   Internet baglantinizi veya yukaridaki mesaji kontrol edin.
    echo ==================================================
)
echo.
pause