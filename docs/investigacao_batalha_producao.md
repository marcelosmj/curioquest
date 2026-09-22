# Investigação em Produção: Travamento da Tela de Batalha (Bloqueio T0)

**Data:** 22 de setembro de 2026  
**Dispositivo:** Xiaomi Redmi Note 11S (`JBHAMZEAWC9H4P9D` / Android)  
**Host Servidor:** `192.168.1.69`  
**Objetivo:** Identificar com precisão por que o cliente mobile oficial trava na tela de carregamento (`LOADING`) ao tentar entrar em combate após o envio de `ENTER_BATTLE`.

---

## 1. Contexto e Hipóteses Anteriores Descartadas
Durante as sessões anteriores (até 18/09), foram refutadas 15 hipóteses com testes empíricos:
1. **Compressão zlib:** Payloads estão abaixo de 32KB.
2. **IDs de structs Thrift:** `ThriftJoinZoneEvent`, `ThriftJoinRoomEvent`, `ThriftRoomListEntry`, `ThriftUserListEntry` batem 100% com as classes compiladas do cliente.
3. **Ordenação de pacotes:** `message_number = -1` (`UNORDERED`) é tratado imediatamente por `checkMessageOrder`.
4. **Assets ausentes:** Cenários como `Stonehenge.jpg` e `Colosseum.jpg` são entregues normalmente via HTTP 200.
5. **Envelope do Plugin:** Respostas de DALC usam `roomLevelPlugin = False`.

---

## 2. Nova Descoberta na Arquitetura do Cliente AS3 (22/09)

### 2.1 O Mecanismo do `TransitionScreen` e `_waitingAsset`
Ao inspecionar `MenuScreen.onEnterGame`:
```actionscript
DialogManager.showDialog(new TransitionScreen(this, this._battleScreen, ... , this._battleScreen.asset), null, false, GameContainer.LAYER_TRANSITION);
```
No `TransitionScreen.as`:
```actionscript
if (Boolean(this._waitingAsset) && !this._waitingAsset.loaded) {
    this._waitingAsset.addEventListener(Event.CHANGE, this.onAssetChange, false, 0, true);
    this._waitingAsset.addEventListener(Event.COMPLETE, this.onAssetLoaded, false, 0, true);
    removeEventListener(Event.ENTER_FRAME, this.onUpdate);
    this.loadingTxt.visible = true;
    ...
    ServerPlugin.startTimeoutTimer();
}
```
Se `this._waitingAsset` (`BattleScreen.asset`) for instanciado mas nunca disparar `Event.COMPLETE`, ou se `fromEsObject` falhar silenciosamente:
1. A tela entra em modo de transição com texto de carregamento (`loadingTxt`, `percTxt`).
2. Se o asset nunca reportar conclusão, a transição é interrompida.
3. Se houver um `TypeError` (exceção não capturada) dentro do ActionScript 3, o Adobe AIR não fecha a aplicação: a execução daquela callstack é abortada e a interface gráfica congela no estado atual a 29fps.

### 2.2 O Ponto Crítico de Falha: `ServerPlugin.getRoom`
Em `BattleScreen.fromEsObject`:
```actionscript
var _loc2_:int = param1.getInteger(EsConstants.ROOM_ID);
var _loc3_:int = param1.getInteger(EsConstants.ROOM_ZONE_ID);
var _loc6_:Room = ServerPlugin.getRoom(_loc3_, _loc2_);
```
E a implementação em `ServerPlugin.as`:
```actionscript
return ES.managerHelper.zoneManager.zoneById(param1).roomById(param2);
```
**Perigo:** Se `zoneById(param1)` retornar `null` (ou seja, se a zona do ElectroServer não foi registrada ou ainda não foi processada no momento em que `BattleScreen.fromEsObject` executa), `zoneById(param1).roomById(param2)` causará imediatamente um **`TypeError: Error #1009` (Null Object Reference)**.

### 2.3 Relação Temporal entre `JoinZoneEvent`, `JoinRoomEvent` e `ENTER_BATTLE`
No servidor atual (`server/game/dalcs/game.py`):
```python
self.send(session, NODE_BATTLE, reply)
session.join_room(BATTLE_ZONE_ID, "battles", battle.room_id, f"node-{node.zone_id}-{node.id}")
self.send(session, ENTER_BATTLE, battle.enter_payload())
```
Todos esses quadros são enfileirados no mesmo segmento TCP em milissegundos. Se `ENTER_BATTLE` for processado antes ou no mesmo frame em que a zona interna do ElectroServer é registrada, ou se a zona enviada não bater com `ROOM_ZONE_ID`, o cliente quebra.

---

## 3. Ações Realizadas Hoje
1. **Controle de Versão:** Inicializado repositório Git com `.gitignore` e diretrizes no workspace (`GEMINI.md` e `.antigravity-rules.json`).
2. **Correção do MerchantDALC:** Corrigida a função `buy_service` para não somar as duas moedas indevidamente, testado roundtrip do codec com sucesso.
3. **Mapeamento do Fluxo de Transição:** Descoberta a relação entre `BattleScreen.asset`, `TransitionScreen` e `ServerPlugin.getRoom`.
