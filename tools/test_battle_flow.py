#!/usr/bin/env python3
"""Automated end-to-end battle test against the local Curio Quest server.
Simulates the exact packet sequence sent and received by the ActionScript 3 client:
1. Connection & Login (Books, Character)
2. GameDALC.NODE_BATTLE (Zone 1, Node 1)
3. JoinZoneEvent & JoinRoomEvent validation
4. ENTER_BATTLE payload validation (BATTLE_CURRENT_PET_INDEX == -1, valid room and zone)
5. Initial BattlePlugin messages: SELECT_PET (p0), SELECT_PET (p1), CURRENT_PLAYER
6. Turn 1 attack: execute basic skill against enemy
7. Turn 2 attack (if needed) until victory
8. Victory verification: RESULTS, rewards, player save check
"""
import logging
import re
import socket
import struct
import sys
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.es5 import esobject, protocol
from server.es5.thrift_binary import ThriftCodec
from server.game.keys import K, NAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("test_battle")

PLATFORM_ANDROID = 1
GAME_DALC = 1
CHARACTER_DALC = 2
BATTLE_PLUGIN = "BattlePlugin"
SERVER_PLUGIN = "ServerPlugin"

LOGIN_PLATFORM = 1
NODE_BATTLE = 1
ENTER_BATTLE = 0

# BattlePlugin Action IDs
SELECT_PET = 2
CURRENT_PLAYER = 3
HEALTH_CHANGE = 4
MANA_CHANGE = 5
COMPLETE = 6
SKILL = 7
RESULTS = 9


def recv_exact(sock, n):
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Server closed connection")
        data += chunk
    return bytes(data)


def read_message(sock, codec):
    (length,) = struct.unpack(">i", recv_exact(sock, 4))
    raw = recv_exact(sock, length)
    indicator, _num, data = protocol.parse_body(raw)
    name = protocol.MESSAGE_TYPES[indicator][0]
    struct_name = protocol.thrift_struct(indicator)
    decoded = codec.decode(struct_name, data) if struct_name in codec.structs else {}
    return name, decoded


def send_message(sock, codec, name, **fields):
    indicator = protocol.INDICATORS[name]
    struct_name = protocol.thrift_struct(indicator)
    encoded = codec.encode(struct_name, fields)
    frame = protocol.build_frame(indicator, 0, encoded)
    sock.sendall(frame)


def main():
    codec = ThriftCodec(ROOT / "server" / "es5" / "thrift_spec.json")

    # 1. HTTP check
    log.info("[1/7] Conectando ao HTTP Server.xml...")
    with urllib.request.urlopen("http://127.0.0.1:8080/pets_live/Server.xml", timeout=5) as resp:
        server_xml = resp.read().decode("utf-8")
    m = re.search(r'host="([^"]+)" port="(\d+)"', server_xml)
    assert m, "Server.xml inválido"
    es_host, es_port = m.group(1), int(m.group(2))
    log.info("Servidor ES5 configurado em %s:%d", es_host, es_port)

    # 2. ES5 TCP Connection
    log.info("[2/7] Conectando ao ElectroServer 5...")
    sock = socket.create_connection((es_host, es_port), timeout=10)
    while recv_exact(sock, 1) != b"\x00":
        pass
    name, msg = read_message(sock, codec)
    assert name == "ConnectionResponse" and msg.get("successful"), f"Conexao falhou: {name} {msg}"
    log.info("[ok] ConnectionResponse recebido (successful=True)")

    # 3. Login
    log.info("[3/7] Enviando LoginRequest...")
    platform = esobject.EsObject().set_integer(K.USER_PLATFORM, PLATFORM_ANDROID)
    send_message(sock, codec, "LoginRequest", userName="BattleTester", clientVersion="5.3.3", clientType="AS3",
                 userVariables={K.USER_PLATFORM: {"encodedEntries": esobject.encode(platform)}})
    name, msg = read_message(sock, codec)
    assert name == "LoginResponse" and msg.get("successful"), f"Login falhou: {name} {msg}"
    login_eso = esobject.decode(msg["esObject"]["encodedEntries"])
    log.info("[ok] LoginResponse recebido: %d Books XML carregados", len(login_eso.get(K.XMLS, [])))

    # 4. Character Login
    log.info("[4/7] Autenticando personagem via CharacterDALC.LOGIN_PLATFORM...")
    char_req = (esobject.EsObject()
                .set_integer(K.ACTION_TYPE, LOGIN_PLATFORM)
                .set_string(K.USER_ID, "battle-tester-device-01")
                .set_string(K.USER_TOKEN, "")
                .set_integer(K.USER_PLATFORM, PLATFORM_ANDROID)
                .set_string(K.CHARACTER_REFER_ID, "")
                .set_string(K.CHARACTER_REREFER_ID, "")
                .set_integer(K.DALC_ID, CHARACTER_DALC))
    send_message(sock, codec, "PluginRequest", pluginName=SERVER_PLUGIN,
                 parameters={"encodedEntries": esobject.encode(char_req)})
    name, msg = read_message(sock, codec)
    assert name == "PluginMessageEvent", f"Esperado PluginMessageEvent, recebido {name}"
    char_reply = esobject.decode(msg["parameters"]["encodedEntries"])
    char_id = char_reply.get(K.CHARACTER_ID)
    energy = char_reply.get(K.CHARACTER_ENERGY)
    log.info("[ok] Personagem logado: ID=%s, Energia=%s", char_id, energy)

    # 5. Enter Battle: Node 1 (Stone Circle)
    log.info("[5/7] Solicitando entrada na Batalha (Zona 1, Nó 1 - Stone Circle)...")
    battle_req = (esobject.EsObject()
                  .set_integer(K.DALC_ID, GAME_DALC)
                  .set_integer(K.ACTION_TYPE, NODE_BATTLE)
                  .set_integer(K.ZONE_ID, 1)
                  .set_integer(K.ZONE_DIFFICULTY, 0)
                  .set_integer(K.ZONE_NODE_ID, 1))
    send_message(sock, codec, "PluginRequest", pluginName=SERVER_PLUGIN,
                 parameters={"encodedEntries": esobject.encode(battle_req)})

    # Receive replies: NODE_BATTLE reply, JoinZoneEvent, JoinRoomEvent, ENTER_BATTLE, and initial BattlePlugin message!
    events_received = []
    initial_battle_msgs = []
    enter_battle_eso = None
    sock.settimeout(6)

    while True:
        try:
            name, msg = read_message(sock, codec)
            events_received.append(name)
            log.info("  <- Evento ES5 recebido: %s", name)

            if name == "PluginMessageEvent":
                plugin = msg.get("pluginName")
                params = esobject.decode(msg["parameters"]["encodedEntries"])
                if plugin == SERVER_PLUGIN:
                    action = params.get(K.ACTION_TYPE)
                    dalc = params.get(K.DALC_ID)
                    if dalc == GAME_DALC and action == ENTER_BATTLE:
                        enter_battle_eso = params
                        log.info("  [ok] ENTER_BATTLE recebido! Room ID: %s, Zone: %s",
                                 params.get(K.ROOM_ID), params.get(K.ZONE_ID))
                    elif dalc == GAME_DALC and action == NODE_BATTLE:
                        log.info("  [ok] NODE_BATTLE resposta recebida (Energia restante: %s)",
                                 params.get(K.CHARACTER_ENERGY))
                elif plugin == BATTLE_PLUGIN:
                    log.info("  [ok] BattlePlugin mensagem recebida! Verificando MESSAGE_LIST...")
                    if params.has(K.MESSAGE_LIST):
                        initial_battle_msgs = params.get(K.MESSAGE_LIST)
                    else:
                        initial_battle_msgs = [params]
                    break
        except socket.timeout:
            break

    assert enter_battle_eso is not None, f"ENTER_BATTLE nao recebido! Eventos: {events_received}"
    assert "JoinZoneEvent" in events_received, "JoinZoneEvent ausente"
    assert "JoinRoomEvent" in events_received, "JoinRoomEvent ausente"

    # VALIDATE ROOT CAUSE FIX IN ENTER_BATTLE
    players_eso = enter_battle_eso.get(K.BATTLE_PLAYERS, [])
    assert len(players_eso) == 2, f"Esperado 2 lados na batalha, recebido {len(players_eso)}"
    for idx, p in enumerate(players_eso):
        cur_pet_idx = p.get(K.BATTLE_CURRENT_PET_INDEX)
        log.info("  Lado %d (%s): BATTLE_CURRENT_PET_INDEX = %s", idx, p.get(K.CHARACTER_NAME), cur_pet_idx)
        assert cur_pet_idx == -1, f"REGRESSAO! BATTLE_CURRENT_PET_INDEX deve ser -1 para nao crashar o AS3 (era {cur_pet_idx})"

    log.info("[ok] VALIDACAO BATTLE_CURRENT_PET_INDEX == -1: SUCESSO! O AS3 nao crasha mais!")

    # Check initial BattlePlugin messages
    action_types = [m.get(K.ACTION_TYPE) for m in initial_battle_msgs]
    log.info("  Acoes iniciais de animacao na fila do BattlePlugin: %s",
             [NAMES.get(a, a) for a in action_types])
    assert SELECT_PET in action_types, "Faltou SELECT_PET para apresentar os Curios na arena!"
    assert CURRENT_PLAYER in action_types, "Faltou CURRENT_PLAYER para indicar o turno do jogador!"

    # 6. Execute Player Turn (Attack!)
    log.info("[6/7] Executando turno de combate: Jogador ataca usando habilidade...")
    battle_zone_id = enter_battle_eso.get(K.ROOM_ZONE_ID)
    battle_room_id = enter_battle_eso.get(K.ROOM_ID)

    turn_count = 0
    battle_won = False

    while turn_count < 10 and not battle_won:
        turn_count += 1
        log.info("--- Turno %d ---", turn_count)
        attack_req = (esobject.EsObject()
                      .set_integer(K.ACTION_TYPE, SKILL)
                      .set_integer(K.BATTLE_SKILL_ID, 2)
                      .set_integer(K.BATTLE_TARGET_PLAYER_INDEX, 1)
                      .set_integer(K.BATTLE_TARGET_PET_INDEX, 0))

        send_message(sock, codec, "PluginRequest", pluginName=BATTLE_PLUGIN,
                     zoneId=battle_zone_id, roomId=battle_room_id,
                     parameters={"encodedEntries": esobject.encode(attack_req)})

        name, msg = read_message(sock, codec)
        assert name == "PluginMessageEvent", f"Esperado PluginMessageEvent apos ataque, recebido {name}"
        turn_params = esobject.decode(msg["parameters"]["encodedEntries"])
        turn_msgs = turn_params.get(K.MESSAGE_LIST, [turn_params]) if turn_params.has(K.MESSAGE_LIST) else [turn_params]

        for m in turn_msgs:
            act = m.get(K.ACTION_TYPE)
            if act == HEALTH_CHANGE:
                p_idx = m.get(K.BATTLE_PLAYER_INDEX)
                hp = m.get(K.BATTLE_PET_CURRENT_HEALTH)
                chg = m.get(K.BATTLE_HEALTH_CHANGE)
                crit = m.get(K.BATTLE_EFFECT_CRIT)
                log.info("    -> Dano! Alvo=%d, Dano=%d, HP Restante=%d (Crit=%s)", p_idx, chg, hp, crit)
            elif act == COMPLETE:
                log.info("    -> [VITORIA!] Mensagem COMPLETE recebida do servidor!")
            elif act == RESULTS:
                battle_won = True
                xp = m.get(K.BATTLE_EXP, 0)
                gold = m.get(K.BATTLE_GOLD, 0)
                items = m.get(K.ITEM_LIST, [])
                log.info("    -> [RESULTADOS!] XP=%d, Ouro=%d, Itens recebidos=%d", xp, gold, len(items))

    assert battle_won, "Batalha nao terminou com vitoria dentro do limite de turnos!"

    # 7. Verify Save game updated
    log.info("[7/7] Verificando persistencia do save apos a vitoria...")
    save_file = ROOT / "server" / "saves" / f"character_{char_id}.json"
    assert save_file.is_file(), f"Arquivo de save nao encontrado em {save_file}"
    save_data = save_file.read_text(encoding="utf-8")
    assert '"node_completes"' in save_data, "node_completes nao registrado no save!"
    log.info("[ok] Save persistido com sucesso! O no da zona foi concluido: %s", save_file.name)

    log.info("=" * 60)
    log.info("SUCESSO TOTAL! CICLO COMPLETO DE BATALHA VALIDADO COM 100%% DE EXITO!")
    log.info("=" * 60)
    sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
