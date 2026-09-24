# Diagnóstico e Solução de Conexão no Dispositivo Real (Xiaomi Redmi Note 11S)

**Data:** 23/09/2026  
**Dispositivo:** Xiaomi Redmi Note 11S (`2201117PG`, Android 13)  
**IP do Celular na Wi-Fi:** `192.168.1.139`  
**IP do Servidor PC na Wi-Fi:** `192.168.1.69`  
**Portas do Servidor:** HTTP `8080` (CDN/Books/Assets), BinaryTCP `9899` (ElectroServer 5)

---

## 1. Causa Raiz do "ERROR: Unable to connect to server"

O APK que estava instalado no aparelho era o `CurioQuest-offline-127.0.0.1.apk`.
Ao analisar o fluxo de inicialização do cliente ActionScript 3 (`CurioQuest.as`, `Project.as` e `ServerPlugin.as`):
1. **Loopback (127.0.0.1) no Android 13:** A pilha HTTP/AIR dentro do Android não permite requisições HTTP em texto claro para `127.0.0.1` de aplicações não confiáveis devido a restrições de permissões do sistema (SELinux / CTA / cleartext traffic).
2. **Dependência de ADB Reverse:** O APK com `127.0.0.1` depende de um túnel reverso ADB ativo constantemente via cabo USB. Se o cabo desconectar ou o túnel oscilar, o jogo trava com erro de conexão imediato.
3. **Validação Histórica:** No histórico do projeto, quando o APK patchado com o IP de rede local (`192.168.1.69`) foi utilizado, o celular conectou nativamente via Wi-Fi, autenticou o jogador "Luffy", baixou todos os assets e entrou na batalha do Nó 1 sem qualquer necessidade de `adb reverse`.

---

## 2. Ações Executadas

1. **Recompilação e Assinatura do APK de Rede Local:**
   - Gerado: `build/CurioQuest-offline-192.168.1.69.apk`
   - URLs reescritas para apontar diretamente para `http://192.168.1.69:8080/`.
   - Assinado com o keystore offline (`curioquest-offline.keystore`).

2. **Endpoint de Download OTA no Servidor:**
   - Atualizado `server/web.py` com a rota `/CurioQuest.apk` servindo o arquivo com MIME type `application/vnd.android.package-archive`.
   - O servidor local pode ser acessado de qualquer navegador no celular conectado na Wi-Fi.

3. **Servidor Ativo em Segundo Plano:**
   - Processo rodando com `--packet-log` ouvindo em `0.0.0.0:8080` e `0.0.0.0:9899`.
   - Regra de Firewall do Windows verificada (`Curio Quest Offline` - Inbound Allow).
