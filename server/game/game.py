"""Game entry point: ElectroServer login, then ServerPlugin and BattlePlugin requests."""
import logging
from pathlib import Path

from ..es5.esobject import EsObject
from ..es5.session import unflatten
from .as3 import as3_date
from .books import BookStore
from .dalc import SERVER_PLUGIN
from .dalcs import ALL_DALCS
from . import progress

JOB_DALC = 9                 # plugins.ServerPlugin ids, for the pushes the client never asks for
ACHIEVEMENT_DALC = 13
from .gamedata import GameData
from .keys import K, NAMES
from .player import PlayerStore

log = logging.getLogger("game")

BATTLE_PLUGIN = "BattlePlugin"


class Game:
    def __init__(self, books_dir, saves_dir, packet_log=False):
        self.books = BookStore(books_dir)
        self.data = GameData(books_dir)
        self.players = PlayerStore(saves_dir)
        self.saves_dir = Path(saves_dir)
        self.packet_log = packet_log
        self.dalcs = {}
        for dalc_class in ALL_DALCS:
            self.register(dalc_class)

    def register(self, dalc_class):
        dalc = dalc_class(self)
        self.dalcs[dalc.dalc_id] = dalc

    async def on_login(self, session, message):
        variables = message.get("userVariables") or {}
        platform = unflatten(variables.get(K.USER_PLATFORM)).get(K.USER_PLATFORM)
        log.info("[%d] login no ElectroServer (plataforma %s)", session.id, platform)
        eso = EsObject()
        eso.set_string(K.SERVER_TIME, as3_date())
        eso.set_string(K.SERVER_ID, "offline")
        eso.set_string(K.SERVER_VERSION, "1.0")
        eso.set_esobject_array(K.XMLS, self.books.esobjects())
        return True, eso, f"player{session.id}"

    async def on_plugin_request(self, session, plugin_name, zone_id, room_id, request):
        if self.packet_log:
            log.info("[%d] <- %s %s", session.id, plugin_name, request.to_debug(NAMES))
        if plugin_name == SERVER_PLUGIN:
            dalc = self.dalcs.get(request.get(K.DALC_ID))
            if dalc is None:
                log.warning("[%d] DALC %s nao implementado (acao %s): %s", session.id, request.get(K.DALC_ID),
                            request.get(K.ACTION_TYPE), request.to_debug(NAMES))
                return
            await dalc.handle(session, request.get(K.ACTION_TYPE), request)
        elif plugin_name == BATTLE_PLUGIN:
            await self.on_battle_request(session, request)
        else:
            log.warning("[%d] plugin desconhecido %r", session.id, plugin_name)

    async def on_battle_request(self, session, request):
        """One battle action from the player, answered with everything the client must animate."""
        battle = session.data.get("battle")
        if battle is None:
            log.warning("[%d] mensagem de batalha sem batalha ativa: %s", session.id, request.to_debug(NAMES))
            return
        battle.handle(request)
        messages = battle.take_messages()
        if messages:
            payload = messages[0] if len(messages) == 1 else EsObject().set_esobject_array(K.MESSAGE_LIST, messages)
            if self.packet_log:
                log.info("[%d] -> BattlePlugin %d mensagem(ns)", session.id, len(messages))
            session.send_plugin_message(BATTLE_PLUGIN, payload, battle.zone_id, battle.room_id)
        if battle.finished:
            self._finish_battle(session, battle)

    def _finish_battle(self, session, battle):
        player = session.data.get("player")
        if player is not None:
            if battle.won:
                self._record_node_win(player, battle.node)
            self._record_progress(session, player, battle)
            self.players.save(player)
        session.data.pop("battle", None)
        log.info("[%d] batalha encerrada (%s)", session.id, "vitoria" if battle.won else "derrota")

    def _record_progress(self, session, player, battle):
        """Feed the jobs and the achievements with what just happened in the battle."""
        stats = battle.stats
        progress.bump(player, "damage", stats["damage"])
        progress.bump(player, "crits", stats["crits"])
        progress.bump(player, "healing", stats["healing"])
        for element, amount in stats["damage_by_element"].items():
            progress.bump(player, "damage:" + element, amount)
        moved = progress.advance_jobs(player, self.data, "fight", target="none")
        if stats["level_ups"]:
            moved += progress.advance_jobs(player, self.data, "level", stats["level_ups"], target="pet")
        if battle.won:
            progress.bump(player, "node_wins", 1)
            progress.bump(player, "gold_earned", (battle.rewards or {}).get("gold", 0))
            progress.bump(player, "exp_earned", (battle.rewards or {}).get("exp", 0))
            moved += progress.advance_jobs(player, self.data, "defeat", target="node")
            for pet in battle.players[1].pets:
                if pet.is_dead:
                    moved += progress.advance_jobs(player, self.data, "defeat", target="pet", pet_type=pet.element)
        self.push_progress(session, player, moved)

    def push_progress(self, session, player, moved_jobs=()):
        """Tell the client what moved: the job panel, then any achievement rank just earned."""
        jobs = self.dalcs.get(JOB_DALC)
        if jobs is not None:
            jobs.push_progress(session, list(moved_jobs))
        achievements = self.dalcs.get(ACHIEVEMENT_DALC)
        updated, awarded = progress.check_achievements(player, self.data)
        if achievements is None:
            return
        achievements.push_updates(session, updated)
        for _ref, entry, items in awarded:
            achievements.push_reward(session, player, entry, items)

    @staticmethod
    def _record_node_win(player, node):
        """Keep the zone progress the client shows after a win."""
        zone = next((z for z in player["zones"]
                     if z["zone_id"] == node.zone_id and z["difficulty"] == node.difficulty), None)
        if zone is None:
            zone = {"zone_id": node.zone_id, "difficulty": node.difficulty, "completes": 0, "node_completes": []}
            player["zones"].append(zone)
        completes = zone["node_completes"]
        while len(completes) <= node.id:
            completes.append(0)
        completes[node.id] += 1
        if node.complete_zone and completes[node.id] >= node.total_health:
            zone["completes"] += 1

    async def on_disconnect(self, session):
        player = session.data.get("player")
        if player is not None:
            self.players.save(player)
