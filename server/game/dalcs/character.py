"""CharacterDALC (DALC_ID 2): login, character creation and account settings."""
import logging
import os
import time

from ...es5.esobject import EsObject
from .. import player as players
from .. import progress, rewards
from ..as3 import as3_date
from ..dalc import Dalc, action
from ..keys import K

log = logging.getLogger("character")

LOGIN_PLATFORM = 1
LOGIN_EMAIL = 2
LOGOUT = 4
CUSTOMIZE = 5
SAVE_TUTORIAL = 6
SAVE_CONFIG = 7
RESET_ZONE = 8
SET_OFFENSE_TEAM = 9
SET_DEFENSE_TEAM = 10
UPGRADE_COOLDOWN_RESET = 13
UPDATE_CURRENCY = 14
DAILY_REWARD = 15
PRIOR_NAME = 24

INVALID_ZONE = 29       # model.utility.ErrorCode (BATTLE_RESTRICTIONS)

NAME_MAX_LENGTH = 20
SERVICE_COOLDOWN = 24   # model.utility.ErrorCode
LOGIN_ERROR = 26


class CharacterDalc(Dalc):
    dalc_id = 2
    name = "CharacterDALC"

    @action(DAILY_REWARD)
    async def daily_reward(self, session, request):
        """One claim a day.  The streak walks the DailyBook, wraps at the last day and starts over
        when a day is missed; DailyWindow only displays what comes back, it decides nothing."""
        player = session.data.get("player")
        data = self.game.data
        if player is None or not data.daily:
            return EsObject().set_integer(K.ACTION_ERROR, LOGIN_ERROR)
        now = time.time()
        today, claimed = int(now // 86400), int(player.get("daily_time", 0) // 86400)
        if claimed == today:
            return EsObject().set_integer(K.ACTION_ERROR, SERVICE_COOLDOWN)
        days = max(1, len(data.daily))
        following = (player.get("daily", 0) + 1) if claimed == today - 1 else 0
        player["daily"] = following % days
        player["daily_time"] = now
        items = []
        for item_id, item_type, quantity in data.daily.get(player["daily"], []):
            if item_type == "grabbag" and item_id in data.grab_bags:
                items += rewards.open_bag(player, data, data.grab_bags[item_id])
            else:
                items.append(rewards.give(player, data, item_id, item_type, quantity))
        log.info("[%d] recompensa diaria do dia %d entregue", session.id, player["daily"])
        self.game.push_progress(session, player)
        self.game.players.save(player)
        return (EsObject().set_integer(K.CHARACTER_DAILY, player["daily"])
                .set_string(K.CHARACTER_DAILY_TIME, as3_date(player["daily_time"]))
                .set_esobject_array(K.ITEM_LIST, items))

    @action(LOGIN_PLATFORM)
    async def login_platform(self, session, request):
        return self._login(session, request.get(K.USER_ID))

    @action(LOGIN_EMAIL)
    async def login_email(self, session, request):
        return self._login(session, request.get(K.CHARACTER_EMAIL) or request.get(K.USER_ID))

    def _login(self, session, device_id):
        # CQ_LOGIN_ERROR=1 answers the login with a plain error instead of the character: if the
        # client shows the error dialog, the plugin message itself is fine and the fault is in
        # the character payload.
        mode = os.environ.get("CQ_LOGIN_ERROR")
        if mode == "1":
            log.warning("[%d] CQ_LOGIN_ERROR=1: erro de login em vez do personagem", session.id)
            return EsObject().set_integer(K.ACTION_ERROR, LOGIN_ERROR)
        game = self.game
        device_id = device_id or f"sem-id-{session.peer[0]}"
        player = game.players.find(device_id)
        if player is None:
            player = players.new_player(game.players.create_id(device_id), device_id, game.data)
            log.info("[%d] personagem novo #%d para o aparelho %s", session.id, player["char_id"], device_id)
        else:
            log.info("[%d] personagem #%d (%s) entrou", session.id, player["char_id"], player["name"] or "sem nome")
        player["last_login"] = time.time()
        progress.ensure_daily_jobs(player, game.data)
        session.data["player"] = player
        payload = players.character_esobject(player, game.data)
        game.players.save(player)
        if mode == "2":
            # full character plus an error: the client decodes everything but stops before
            # building the Character, which tells decoding and character building apart
            log.warning("[%d] CQ_LOGIN_ERROR=2: personagem completo marcado como erro", session.id)
            payload.set_integer(K.ACTION_ERROR, LOGIN_ERROR)
        return payload

    @action(LOGOUT)
    async def logout(self, session, request):
        self.game.players.save(session.data["player"])
        return EsObject()

    @action(CUSTOMIZE)
    async def customize(self, session, request):
        player = session.data["player"]
        name = " ".join(str(request.get(K.CHARACTER_NAME) or "").split())[:NAME_MAX_LENGTH]
        if name:
            # MenuProfilePanel prices the next rename off how many names came before
            # (getServiceBasedOnPriorNameChanges), so the history has to be kept - see PRIOR_NAME.
            previous = player.get("name")
            if previous and previous != name:
                player.setdefault("prior_names", []).append(
                    {"name": previous, "until": as3_date(time.time())})
            player["name"] = name
        # the client sends the gender as a Boolean here but reads it back as "M"/"F"
        player["gender"] = "M" if request.get(K.CHARACTER_GENDER) else "F"
        self.game.players.save(player)
        return EsObject().set_string(K.CHARACTER_NAME, player["name"]).set_string(K.CHARACTER_GENDER, player["gender"])

    @action(PRIOR_NAME)
    async def prior_name(self, session, request):
        """MenuProfilePanel calls showLoading() before asking and only hides it when this answers.

        Leaving it unanswered froze the whole session: the panel span its LOADING dialog until the
        client's 60s timeout closed the connection.  An empty list is the right answer for a player
        who never renamed - the panel reads only the LENGTH, to price the next change.
        """
        player = session.data["player"]
        names = [EsObject()
                 .set_integer(K.CHARACTER_ID, player["id"])
                 .set_string(K.PREVIOUS_NAME, entry["name"])
                 .set_string(K.LAST_DATE_NAME_WAS_VALID, entry["until"])
                 for entry in player.get("prior_names", [])]
        return EsObject().set_esobject_array(K.PRIOR_NAMES, names)

    @action(SAVE_TUTORIAL)
    async def save_tutorial(self, session, request):
        player = session.data["player"]
        player["tutorial"] = [bool(state) for state in request.get(K.CHARACTER_TUTORIAL_STATES, [])]
        self.game.players.save(player)

    @action(SAVE_CONFIG)
    async def save_config(self, session, request):
        player = session.data["player"]
        player["global_chat"] = bool(request.get(K.CHARACTER_GLOBAL_CHAT_ENABLED, False))
        player["friend_requests"] = bool(request.get(K.CHARACTER_FRIEND_REQUESTS_ENABLED, True))
        player["chat_channel"] = int(request.get(K.CHARACTER_CHAT_CHANNEL, 0))
        player["battle_speed"] = max(1, int(request.get(K.CHARACTER_BATTLE_SPEED, 1)))
        self.game.players.save(player)

    @action(RESET_ZONE)
    async def reset_zone(self, session, request):
        """Start a zone over.

        ZoneWindow.onResetZone reads nothing out of the reply: it calls clearNodes() and redraws
        on its own, and only shows an error if ACTION_ERROR is present.  So all the server owes is
        forgetting the completes - but it DOES owe an answer: the action has a case in the client's
        parse, so staying silent leaves the window spinning until the 60s timeout kills the session.
        """
        player = session.data.get("player")
        if player is None:
            return EsObject().set_integer(K.ACTION_ERROR, LOGIN_ERROR)
        zone_id = int(request.get(K.ZONE_ID, 0))
        difficulty = int(request.get(K.ZONE_DIFFICULTY, 0))
        if (zone_id, difficulty) not in self.game.data.zone_ids:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ZONE)
        # a zone only gets a save record on the first node battle (game.py), so a player who has
        # never played it has nothing to clear - that is success, not an error
        zone = next((z for z in player["zones"]
                     if z["zone_id"] == zone_id and z["difficulty"] == difficulty), None)
        if zone is not None:
            zone["node_completes"] = [0] * len(zone["node_completes"])
            zone["completes"] = 0
            self.game.players.save(player)
        log.info("[%d] zona %d/%d reiniciada", session.id, zone_id, difficulty)
        return EsObject()

    @action(UPDATE_CURRENCY)
    async def update_currency(self, session, request):
        """Re-read the wallet.  Supersonic and CreditPopupBase take nothing but CHARACTER_CREDITS."""
        player = session.data.get("player")
        if player is None:
            return EsObject().set_integer(K.ACTION_ERROR, LOGIN_ERROR)
        return EsObject().set_integer(K.CHARACTER_CREDITS, player["credits"])

    @action(SET_OFFENSE_TEAM)
    async def set_offense_team(self, session, request):
        return self._set_team(session, request, "offense_team")

    @action(SET_DEFENSE_TEAM)
    async def set_defense_team(self, session, request):
        return self._set_team(session, request, "defense_team")

    def _set_team(self, session, request, field):
        player = session.data["player"]
        team_id = int(request.get(K.TEAM_ID, 0))
        if 0 <= team_id < player["teams_max"]:
            player[field] = team_id
            self.game.players.save(player)
        return EsObject().set_integer(K.TEAM_ID, player[field])
