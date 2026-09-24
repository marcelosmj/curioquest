"""Player saves (one JSON file per character) and the character payload the client reads
in model.character.Character.fromEsObject and the classes it calls."""
import json
import logging
import os
import threading
import time
from pathlib import Path

from ..es5 import esobject as es_types
from ..es5.esobject import EsObject
from .as3 import as3_date
from .keys import K

log = logging.getLogger("player")

NEW_PLAYER = {"gold": 500, "credits": 25, "energy": 20, "tokens": 5, "tickets": 5, "rating": 1000, "teams_max": 3}

TUTORIAL_STATES = 57    # model.tutorial.Tutorial uses states 0..56

# (save field, max variable, cooldown variable) for values that refill over time
REFILLS = (("energy", "energyMax", "energyCooldown"), ("tokens", "tokenMax", "tokenCooldown"),
           ("tickets", "ticketMax", "ticketCooldown"))


class PlayerStore:
    def __init__(self, saves_dir):
        self.dir = Path(saves_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._index_path = self.dir / "index.json"
        if self._index_path.exists():
            self._index = json.loads(self._index_path.read_text(encoding="utf-8"))
        else:
            self._index = {"next_char_id": 1, "devices": {}}
        # One player dict per character, SHARED by every session holding it.  Without this each
        # login got its own json.loads copy and on_disconnect wrote that copy back, so two
        # sessions for the same device silently clobbered each other - a purchase that had
        # already answered with the new balance could vanish on the next disconnect.
        self._cache = {}

    def _path(self, char_id):
        return self.dir / f"character_{char_id}.json"

    def find(self, device_id):
        char_id = self._index["devices"].get(device_id)
        if char_id is None or not self._path(char_id).exists():
            return None
        with self._lock:
            player = self._cache.get(char_id)
            if player is None:
                player = json.loads(self._path(char_id).read_text(encoding="utf-8"))
                self._cache[char_id] = player
            return player

    def create_id(self, device_id):
        with self._lock:
            char_id = self._index["next_char_id"]
            self._index["next_char_id"] = char_id + 1
            self._index["devices"][device_id] = char_id
            self._write(self._index_path, self._index)
        return char_id

    def save(self, player):
        # keep the shared copy authoritative: a session that created the player (rather than
        # loading it) must land in the cache too, or the next login would read a stale file
        self._cache[player["char_id"]] = player
        self._write(self._path(player["char_id"]), player)

    @staticmethod
    def _write(path, data):
        content = json.dumps(data, indent=1, ensure_ascii=False)
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(path)
        except Exception:
            try:
                path.write_text(content, encoding="utf-8")
            except Exception as e:
                log.error("Erro salvando %s: %s", path, e)


def new_player(char_id, device_id, data):
    now = time.time()
    player = {
        "char_id": char_id, "device_id": device_id, "player_id": f"CQ{char_id:05d}",
        "name": "", "gender": "F", "created": now, "last_login": now,
        "level": 1, "bps": 0, "exp": 0, "dust": 0, "pet_max_bonus": 0,
        "zone_id": 1, "zone_difficulty": 0, "offense_team": 0, "defense_team": 0,
        "battle_speed": 1, "global_chat": False, "friend_requests": True, "chat_channel": 0,
        "daily": 0, "daily_time": 0, "num_spins": 0, "num_free_spins": 0,
        "tutorial": [], "next_pet_uid": 1, "pets": [], "teams": [], "zones": [], "inventory": [],
        "jobs_active": [], "jobs_complete": [], "achievements": [],
        **NEW_PLAYER,
    }
    for field, _max, _cooldown in REFILLS:
        player[field + "_updated"] = now
    for species_id in data.starter_ids():
        add_pet(player, data, species_id)
    team_size = data.var("petTeamSize", 3)
    player["teams"] = [{"id": 0, "name": "", "pet_uids": [p["uid"] for p in player["pets"]][:team_size]}]
    return player


def exp_for_level(level, size=1):
    """The curve the client draws the experience bar with (model.pet.PetRef.getExpFromLevel)."""
    return 0 if level <= 1 else int(75 * 0.8 * (level - 1) ** 2 * size)


def grant_exp(pet, species, data, amount):
    """Pour experience into one curio and level it up as far as the curve allows.

    Lives here so the battle rewards and the experience the player spends by hand agree on the
    rule; returns how many levels it gained.
    """
    if amount <= 0:
        return 0
    pet["exp"] += amount
    gained, top = 0, data.max_level(species, pet["prestige"])
    while pet["level"] < top and pet["exp"] >= exp_for_level(pet["level"] + 1, species.size):
        pet["level"] += 1
        pet["skill_points"] += 1
        gained += 1
    return gained


def add_pet(player, data, species_id, level=1):
    species = data.species[species_id]
    uid = player["next_pet_uid"]
    player["next_pet_uid"] = uid + 1
    # the client indexes skill ranks by skill id, and an empty skill slot is a 0
    ranks = [0] * (max([skill.id for skill in species.skills], default=0) + 1)
    for skill in species.skills:
        ranks[skill.id] = skill.start_rank
    slots = [skill.id for skill in species.skills if skill.start_rank > 0]
    slot_count = data.var("skillSlots", 4)
    pet = {
        "uid": uid, "species": species_id, "name": "", "prestige": 0, "rank": 0, "fusion": 0,
        "level": level, "exp": 0, "skin": 0, "skill_points": 0, "fatigue": 0,
        # permanent stat gains from consumables, by stat name (PetData reads them back at login)
        "bonus": {},
        # equipped enchants by slot id (EnchantRef: 1 red, 2 yellow, 3 blue); 0 means empty
        "enchants": {},
        "skill_ranks": ranks,
        "skill_slots": (slots[:slot_count] + [0] * slot_count)[:slot_count],
    }
    player["pets"].append(pet)
    return pet


def refill(player, data, now=None):
    """Apply time-based refills; returns {field: client countdown in ms (negative while refilling)}."""
    now = now or time.time()
    countdowns = {}
    for field, max_var, cooldown_var in REFILLS:
        maximum, cooldown_ms = data.var(max_var), data.var(cooldown_var)
        stamp = player.get(field + "_updated", now)
        if cooldown_ms <= 0 or player[field] >= maximum:
            player[field + "_updated"] = now
            countdowns[field] = 0
            continue
        gained = int((now - stamp) * 1000 // cooldown_ms)
        if gained:
            player[field] = min(maximum, player[field] + gained)
            stamp += gained * cooldown_ms / 1000
            player[field + "_updated"] = stamp
        if player[field] >= maximum:
            player[field + "_updated"] = now
            countdowns[field] = 0
        else:
            countdowns[field] = -(cooldown_ms - (now - stamp) * 1000)
    return countdowns


def pet_esobject(pet):
    eso = EsObject()
    eso.set_integer(K.PET_UID, pet["uid"])
    eso.set_integer(K.PET_ID, pet["species"])
    eso.set_string(K.PET_NAME, pet["name"])
    for key, field in (("PET_PRESTIGE", "prestige"), ("PET_RANK", "rank"), ("PET_FUSION", "fusion"),
                       ("PET_LEVEL", "level"), ("PET_EXP", "exp"), ("PET_SKIN", "skin"),
                       ("PET_SKILL_POINTS", "skill_points"), ("PET_FATIGUE", "fatigue")):
        eso.set_integer(getattr(K, key), pet[field])
    # .get, not [], because curios saved before consumables existed have no bonus block
    bonus = pet.get("bonus") or {}
    for key, stat in (("PET_BONUS_HEALTH", "health"), ("PET_BONUS_DAMAGE", "damage"),
                      ("PET_BONUS_HEALING", "healing"), ("PET_BONUS_MANA", "mana"),
                      ("PET_BONUS_LUCK", "luck")):
        eso.set_integer(getattr(K, key), int(bonus.get(stat, 0)))
    # A promoted curio carries its own rarity: PetData.fromEsObject takes PET_RARITY when it is
    # present and falls back to the species' rarity (NO_RARITY_FROM_DATABASE) when it is not, so
    # only curios that were actually promoted need the key.
    if pet.get("rarity"):
        eso.set_integer(K.PET_RARITY, int(pet["rarity"]))
    # equipped enchants, one key per colour.  Only the singular keys go out: the client reads
    # each of them behind doesPropertyExist, and the plural PET_*_ENCHANTS lists are left alone.
    enchants = pet.get("enchants") or {}
    for key, slot in (("PET_RED_ENCHANT", 1), ("PET_YELLOW_ENCHANT", 2), ("PET_BLUE_ENCHANT", 3)):
        eso.set_integer(getattr(K, key), int(enchants.get(str(slot), enchants.get(slot, 0)) or 0))
    eso.set_integer_array(K.PET_SKILL_RANKS, pet["skill_ranks"])
    eso.set_integer_array(K.PET_SKILL_SLOTS, pet["skill_slots"])
    eso.set_number(K.PET_FATIGUE_MILLISECONDS, 0)
    return eso


def character_esobject(player, data, now=None):
    """The character the client reads in model.character.Character.fromEsObject.

    Set CQ_SKIP=CHARACTER_PETS,CHARACTER_ZONES (client-side names) to leave parts out; that
    is how we bisect which part of the payload the real client chokes on.
    """
    now = now or time.time()
    countdowns = refill(player, data, now)
    eso = EsObject()
    eso.set_integer(K.CHARACTER_ID, player["char_id"])
    eso.set_string(K.CHARACTER_NAME, player["name"])
    eso.set_string(K.CHARACTER_GENDER, player["gender"])
    for key, field in (("CHARACTER_BPS", "bps"), ("CHARACTER_LEVEL", "level"), ("CHARACTER_ENERGY", "energy"),
                       ("CHARACTER_TOKENS", "tokens"), ("CHARACTER_TICKETS", "tickets"), ("CHARACTER_RATING", "rating"),
                       ("CHARACTER_GOLD", "gold"), ("CHARACTER_CREDITS", "credits"), ("CHARACTER_EXP", "exp"),
                       ("CHARACTER_DUST", "dust"), ("CHARACTER_ZONE_ID", "zone_id"),
                       ("CHARACTER_ZONE_DIFFICULTY", "zone_difficulty"), ("CHARACTER_OFFENSE_TEAM_ID", "offense_team"),
                       ("CHARACTER_DEFENSE_TEAM_ID", "defense_team"), ("CHARACTER_TEAMS_MAX", "teams_max"),
                       ("CHARACTER_NUM_SPINS", "num_spins"), ("CHARACTER_NUM_FREE_SPINS", "num_free_spins"),
                       ("CHARACTER_DAILY", "daily"), ("CHARACTER_CHAT_CHANNEL", "chat_channel"),
                       ("CHARACTER_BATTLE_SPEED", "battle_speed"), ("CHARACTER_PET_MAX_BONUS", "pet_max_bonus")):
        eso.set_integer(getattr(K, key), player[field])
    eso.set_boolean(K.CHARACTER_MODERATOR, False)
    eso.set_boolean(K.CHARACTER_ADMIN, False)
    eso.set_string(K.CHARACTER_USERNAME, player["name"])
    eso.set_string(K.CHARACTER_PLAYER_ID, player["player_id"])
    eso.set_number(K.CHARACTER_SPIN_MILLISECONDS, 0)
    eso.set_number(K.CHARACTER_UPGRADE_MILLISECONDS, 0)
    eso.set_number(K.CHARACTER_ENERGY_MILLISECONDS, countdowns["energy"])
    eso.set_number(K.CHARACTER_TOKEN_MILLISECONDS, countdowns["tokens"])
    eso.set_number(K.CHARACTER_TICKET_MILLISECONDS, countdowns["tickets"])
    eso.set_string(K.CHARACTER_CREATE_TIME, as3_date(player["created"]))
    eso.set_string(K.CHARACTER_DAILY_TIME, as3_date(player["daily_time"]))
    eso.set_string(K.CHARACTER_CHAT_MUTE_TIME, as3_date(0))
    eso.set_boolean(K.CHARACTER_GLOBAL_CHAT_ENABLED, player["global_chat"])
    eso.set_boolean(K.CHARACTER_FRIEND_REQUESTS_ENABLED, player["friend_requests"])
    # the client reads tutorial states by index, so always send the whole array
    states = list(player["tutorial"])
    states += [False] * (TUTORIAL_STATES - len(states))
    eso.set_boolean_array(K.CHARACTER_TUTORIAL_STATES, states)

    eso.set_esobject_array(K.CHARACTER_INVENTORY_ITEMS, [
        EsObject().set_integer(K.ITEM_ID, item["id"]).set_integer(K.ITEM_TYPE, item["type"])
        .set_integer(K.ITEM_QTY, item["qty"]).set_integer(K.PET_PRESTIGE, 0).set_integer(K.PET_SKIN, 0)
        for item in player["inventory"] if item["qty"] > 0])
    eso.set_esobject_array(K.CHARACTER_PETS, [pet_esobject(pet) for pet in player["pets"] if pet["species"] in data.species])
    eso.set_esobject_array(K.CHARACTER_TEAMS, [
        EsObject().set_integer(K.TEAM_ID, team["id"]).set_string(K.TEAM_NAME, team["name"])
        .set_integer_array(K.TEAM_PET_UIDS, team["pet_uids"])
        for team in player["teams"]])
    # the zone map reads this without checking, so every zone/difficulty needs an entry
    saved_zones = {(zone["zone_id"], zone["difficulty"]): zone for zone in player["zones"]}
    eso.set_esobject_array(K.CHARACTER_ZONES, [
        EsObject().set_integer(K.ZONE_ID, zone_id).set_integer(K.ZONE_DIFFICULTY, difficulty)
        .set_integer(K.ZONE_COMPLETES, saved.get("completes", 0))
        .set_integer_array(K.ZONE_NODE_COMPLETES, saved.get("node_completes", []))
        for (zone_id, difficulty) in data.zone_ids
        for saved in [saved_zones.get((zone_id, difficulty), {})]])
    eso.set_esobject_array(K.CHARACTER_FRIENDS, [])
    eso.set_esobject_array(K.CHARACTER_REQUESTS, [])
    eso.set_esobject_array(K.CHARACTER_CHAT_IGNORES, [])
    eso.set_esobject_array(K.CHARACTER_JOBS_ACTIVE, [
        EsObject().set_integer(K.JOB_ID, job["id"]).set_integer(K.JOB_PROGRESS, job["progress"])
        .set_boolean(K.JOB_ISLOOTED, job["looted"])
        for job in player["jobs_active"] if not job["looted"]])
    eso.set_integer_array(K.CHARACTER_JOBS_COMPLETE, player["jobs_complete"])
    eso.set_string(K.LAST_DAILY_JOB_UPDATE_TIME, as3_date(now))
    eso.set_string(K.CHARACTER_LAST_LOGIN, as3_date(player["last_login"]))
    eso.set_esobject_array(K.CHARACTER_TIMED_MODIFIERS, [])
    eso.set_esobject_array(K.CHARACTER_LIMITED_OFFERS, [])
    eso.set_esobject_array(K.CHARACTER_VIDEO_OFFERS, [])
    eso.set_esobject_array(K.CHARACTER_ACHIEVEMENTS, [
        EsObject().set_integer(K.ACHIEVEMENT_ID, entry["id"])
        .set_integer(K.ACHIEVEMENT_PROGRESS, entry["progress"]).set_integer(K.ACHIEVEMENT_RANK, entry["rank"])
        for entry in player.get("achievements", [])])

    size = max(list(data.species) + [0]) + 1
    collection = {name: [0] * size for name in ("level", "prestige", "rank", "fusion")}
    for pet in player["pets"]:
        if pet["species"] < size:
            for name in collection:
                collection[name][pet["species"]] = max(collection[name][pet["species"]], pet[name])
    eso.set_esobject(K.PET_COLLECTION, EsObject()
                     .set_integer_array(K.PET_LEVELS, collection["level"])
                     .set_integer_array(K.PET_PRESTIGES, collection["prestige"])
                     .set_integer_array(K.PET_RANKS, collection["rank"])
                     .set_integer_array(K.PET_FUSIONS, collection["fusion"]))

    _debug_filters(eso)
    return eso


# Empty stand-ins by wire type, for CQ_EMPTY (see character_esobject).
_EMPTY = {
    es_types.ESOBJECT_ARRAY: lambda eso, key: eso.set_esobject_array(key, []),
    es_types.INTEGER_ARRAY: lambda eso, key: eso.set_integer_array(key, []),
    es_types.BOOLEAN_ARRAY: lambda eso, key: eso.set_boolean_array(key, []),
    es_types.STRING_ARRAY: lambda eso, key: eso.set_string_array(key, []),
    es_types.ESOBJECT: lambda eso, key: eso.set_esobject(key, EsObject()),
    es_types.STRING: lambda eso, key: eso.set_string(key, ""),
    es_types.INTEGER: lambda eso, key: eso.set_integer(key, 0),
}


NEUTRAL_DATE = "Mon Jan 1 00:00:00 GMT+0000 2024"


def _neutralise(eso):
    """CQ_NEUTRAL=1: keep every key and type, but send harmless values for the dates and the
    millisecond counters, so those can be ruled out without changing the shape of the payload."""
    for key in eso.keys():
        kind, value = eso.get_type(key), eso.get(key)
        if kind == es_types.NUMBER:
            eso.set_number(key, 0)
        elif kind == es_types.STRING and "GMT+" in str(value):
            eso.set_string(key, NEUTRAL_DATE)
    log.warning("CQ_NEUTRAL: datas e contadores do personagem zerados")


def _debug_filters(eso):
    """CQ_SKIP drops keys, CQ_EMPTY blanks them: both take client-side names, comma separated."""
    if os.environ.get("CQ_NEUTRAL"):
        _neutralise(eso)
    zone = os.environ.get("CQ_ZONE")
    if zone:
        # point the character at a zone that does not exist: the client then builds no zone
        # map at all and goes straight to character creation
        eso.set_integer(K.CHARACTER_ZONE_ID, int(zone))
        log.warning("CQ_ZONE: personagem apontado para a zona %s", zone)
    if os.environ.get("CQ_SHORT_COLLECTION") and eso.has(K.PET_COLLECTION):
        # same keys, zero-length arrays: rules the pet collection in or out
        collection = eso.get(K.PET_COLLECTION)
        for key in collection.keys():
            collection.set_integer_array(key, [])
        log.warning("CQ_SHORT_COLLECTION: colecao de curios enviada vazia")
    for variable, action in (("CQ_SKIP", "removido"), ("CQ_EMPTY", "esvaziado")):
        for name in (part.strip() for part in os.environ.get(variable, "").split(",")):
            key = getattr(K, name, None) if name else None
            if not key or not eso.has(key):
                continue
            if variable == "CQ_SKIP":
                eso.remove(key)
            else:
                empty = _EMPTY.get(eso.get_type(key))
                if empty is None:
                    log.warning("CQ_EMPTY: %s e do tipo %s, nao sei esvaziar", name, eso.get_type(key))
                    continue
                empty(eso, key)
            log.warning("%s: %s %s do personagem", variable, name, action)
