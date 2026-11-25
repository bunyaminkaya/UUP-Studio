@echo off
setlocal
cd /d "%~dp0"
rem ---- Gerekli paketler
python -m pip install -r requirements.txt pyinstaller || goto :err
python tools\make_icon.py
for /f %%v in ('python tools\make_version.py') do set VER=%%v
echo Surum: %VER%

rem ---- EXE (klasor modu: Qt LGPL gereklerine uygun)
python -m PyInstaller --noconfirm --clean --windowed --uac-admin --name "UUP Studio" ^
  --icon assets\icon.ico --version-file build\version_info.txt ^
  --add-data "locales;locales" main.py || goto :err

rem ---- Istege bagli kod imzalama: SIGN_PFX (pfx yolu) ve SIGN_PASS ortam degiskenlerini tanimlayin
if defined SIGN_PFX (
  echo EXE imzalaniyor...
  signtool sign /f "%SIGN_PFX%" /p "%SIGN_PASS%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 ^
    "dist\UUP Studio\UUP Studio.exe" || goto :err
) else (
  echo UYARI: SIGN_PFX tanimli degil, EXE imzasiz. SmartScreen uyari verebilir.
)

rem ---- Belgeleri pakete ekle
copy /y THIRD_PARTY.md "dist\UUP Studio\" >nul
copy /y CHANGELOG.md "dist\UUP Studio\" >nul
copy /y README.md "dist\UUP Studio\" >nul

rem ---- Surum numarali zip
if exist "dist\UUP_Studio_%VER%.zip" del "dist\UUP_Studio_%VER%.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\UUP Studio' -DestinationPath 'dist\UUP_Studio_%VER%.zip'" || goto :err

rem ---- Kurulum paketi (Inno Setup kuruluysa)
where ISCC >nul 2>nul
if %errorlevel%==0 (
  ISCC /DMyAppVersion=%VER% installer.iss || goto :err
  if defined SIGN_PFX signtool sign /f "%SIGN_PFX%" /p "%SIGN_PASS%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "dist\UUP_Studio_Setup_%VER%.exe"
) else (
  echo Bilgi: Inno Setup (ISCC) bulunamadi, kurulum paketi atlandi. Zip hazir.
)

echo.
echo Hazir: dist\UUP Studio\UUP Studio.exe
echo Zip:   dist\UUP_Studio_%VER%.zip
goto :eof
:err
echo Derleme basarisiz oldu.
exit /b 1
