# Aprendizado: Wi-Fi LAN vs ADB Reverse no Dispositivo Físico

## Problema
O app no Android 13 exibia "ERROR: Unable to connect to server [ RECONNECT ]" logo após a inicialização.

## Causa
1. O APK compilado com `--host 127.0.0.1` depende de `adb reverse tcp:8080 tcp:8080` e `tcp:9899 tcp:9899`.
2. O subsistema de rede do Adobe AIR no Android 13 sofre restrições de permissões para tráfego cleartext em `127.0.0.1`.
3. Qualquer oscilação ou desconexão do cabo USB derruba a comunicação.

## Solução
- Gerar o APK com `--host 192.168.1.69` (IP local do computador na Wi-Fi).
- Garantir que o celular esteja na mesma rede Wi-Fi (`192.168.1.x`).
- Disponibilizar rota de download direto OTA (`/CurioQuest.apk`) no servidor HTTP `8080`.
