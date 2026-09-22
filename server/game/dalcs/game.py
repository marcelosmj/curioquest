"""GameDALC (DALC_ID 1): entering node battles, plus the small housekeeping calls."""
import logging
import os

from ...es5.esobject import EsObject
from ..battle import Battle
from ..dalc import Dalc, action
from ..keys import K
from .. import player as players

log = logging.getLogger("gamedalc")

ENTER_BATTLE = 0
NODE_BATTLE = 1
NOTIFICATION = 2
XML_UPDATE = 4
IDLE = 5
DISCONNECT = 6
ALL_EVENTS_STATUS = 7

NOT_ENOUGH_ENERGY = 25          # model.utility.ErrorCode
BATTLE_RESTRICTIONS = 29
BATTLE_ZONE_ID = 1              # ElectroServer zone that holds the battle rooms


class GameDalc(Dalc):
    dalc_id = 1
    name = "GameDALC"

    def __init__(self, game):
        super().__init__(game)
        self._next_room = 1

    @action(NODE_BATTLE)
    async def node_battle(self, session, request):
        player = session.data.get("player")
        if player is None:
            return EsObject().set_integer(K.ACTION_ERROR, BATTLE_RESTRICTIONS)
        key = (int(request.get(K.ZONE_ID, 0)), int(request.get(K.ZONE_DIFFICULTY, 0)),
               int(request.get(K.ZONE_NODE_ID, 0)))
        node = self.game.data.nodes.get(key)
        if node is None:
            log.warning("[%d] no inexistente: %s", session.id, key)
            return EsObject().set_integer(K.ACTION_ERROR, BATTLE_RESTRICTIONS)

        completes = self._node_completes(player, node)
        battle_index, battle_ref = self._current_battle(node, completes)
        if battle_ref is None:
            return EsObject().set_integer(K.ACTION_ERROR, BATTLE_RESTRICTIONS)

        countdowns = players.refill(player, self.game.data)
        if player["energy"] < node.energy:
            return EsObject().set_integer(K.ACTION_ERROR, NOT_ENOUGH_ENERGY)
        player["energy"] -= node.energy
        self.game.players.save(player)

        battle = Battle(self.game, player, node, battle_ref, battle_index, self._next_room, BATTLE_ZONE_ID)
        self._next_room += 1
        session.data["battle"] = battle
        log.info("[%d] batalha no no '%s' (%s) contra %d curios", session.id, node.name, key, len(battle.players[1].pets))

        # the reply updates the energy counter, then the client needs the room before the battle
        reply = (EsObject().set_integer(K.CHARACTER_ENERGY, player["energy"])
                 .set_number(K.CHARACTER_ENERGY_MILLISECONDS, countdowns["energy"]))
        self.send(session, NODE_BATTLE, reply)
        # medido no aparelho em 2026-09-18: enviar ou nao este par nao muda nada, o cliente ignora
        # o ENTER_BATTLE dos dois jeitos - o travamento esta noutro lugar
        session.join_room(BATTLE_ZONE_ID, "battles", battle.room_id, f"node-{node.zone_id}-{node.id}")
        self.send(session, ENTER_BATTLE, battle.enter_payload())

    @action(IDLE)
    async def idle(self, session, request):
        return None

    @action(DISCONNECT)
    async def disconnect(self, session, request):
        player = session.data.get("player")
        if player is not None:
            self.game.players.save(player)
        return None

    @action(ALL_EVENTS_STATUS)
    async def all_events_status(self, session, request):
        return EsObject()

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _node_completes(player, node):
        for zone in player["zones"]:
            if zone["zone_id"] == node.zone_id and zone["difficulty"] == node.difficulty:
                completes = zone["node_completes"]
                return completes[node.id] if node.id < len(completes) else 0
        return 0

    @staticmethod
    def _current_battle(node, completes):
        """Nodes with several fights advance one fight per win, like ZoneNodeRef.getCurrentBattleRef."""
        total = 0
        for index, battle in enumerate(node.battles):
            total += max(0, battle.health)
            if completes < total or battle.health <= 0:
                return index, battle
        return len(node.battles), None
