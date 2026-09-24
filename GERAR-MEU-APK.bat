@echo off
chcp 65001 >nul
echo.
echo  Curio Quest - gerador do seu APK
echo  ================================
echo.
echo  Detecta o IP deste PC e monta um APK que fala com ele pelo Wi-Fi.
echo  (Se voce for ligar o celular por cabo USB, nao precisa disto:
echo   use o CurioQuest-offline-127.0.0.1.apk que ja veio pronto.)
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo  [X] Python nao encontrado. Instale em https://python.org e marque
  echo      "Add Python to PATH" durante a instalacao.
  echo.
  pause
  exit /b 1
)

where java >nul 2>&1
if errorlevel 1 (
  echo  [X] Java nao encontrado. E necessario para assinar o APK.
  echo      Instale o Temurin JDK: https://adoptium.net
  echo.
  pause
  exit /b 1
)

if not exist "Curio Quest_1.15.00.apk" (
  echo  [X] Falta o arquivo "Curio Quest_1.15.00.apk" nesta pasta.
  echo      Ele vem junto no pacote, dentro de apk\. Copie para ca.
  echo.
  pause
  exit /b 1
)

python tools\patch_apk.py
if errorlevel 1 (
  echo.
  echo  [X] Falhou. Leia a mensagem acima.
  pause
  exit /b 1
)

echo.
echo  Pronto. O seu APK esta na pasta build\.
echo.
echo  Agora instale no celular:
echo    adb install -r build\CurioQuest-offline-SEU-IP.apk
echo    adb shell pm clear air.com.A5thplanetgames.pets
echo.
pause
