"""PetDALC (DALC_ID 8): naming, teams, skins and the skill tree."""
import logging

from ...es5.esobject import EsObject
from ..dalc import Dalc, action
from ..keys import K
from .. import progress, rewards
from .. import player as players
from ..player import exp_for_level

log = logging.getLogger("petdalc")

PET_NAME = 1
SAVE_TEAM = 2
SAVE_TEAM_NAME = 3
USE_CONSUMABLE = 4
USE_ENCHANT = 10
FUSION = 16
RARITY_PROMOTE = 17
RARITY_SUMMON = 18
REMOVE_ENCHANT = 14
UPGRADE_ENCHANT = 15

SLOT_KEYS = {1: "PET_RED_ENCHANT", 2: "PET_YELLOW_ENCHANT", 3: "PET_BLUE_ENCHANT"}

# MaterialBook hard-codes these ids as the epic/legendary/mythic core fragments
CORE_MATERIALS = (48, 49, 50)
UPGRADE_SKILL = 5
SAVE_SKILL_SLOTS = 6
USE_EXP = 9
SAVE_SKIN = 8
PRESTIGE = 7
PETS_COLLECTED = 12
UPGRADE_RANK = 13
EXCHANGE_PETS_CORES = 20        # the only exchange PetExchangeWindow ever sends

INVALID_PET = 7                 # model.utility.ErrorCode
INSUFFICIENT_FUNDS = 8
PET_ON_OFFENSE_TEAM = 58

NAME_MAX_LENGTH = 20


class PetDalc(Dalc):
    """Actions 3, 6 and 12 have no case in the client's PetDALC.parse: the client already applied
    the change on screen and only needs it stored, so they are answered with silence."""
    dalc_id = 8
    name = "PetDALC"

    @action(PET_NAME)
    async def pet_name(self, session, request):
        player, pet = self._pet(session, request)
        if pet is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        pet["name"] = (request.get(K.PET_NAME) or "").strip()[:NAME_MAX_LENGTH]
        self.game.players.save(player)
        return EsObject().set_string(K.PET_NAME, pet["name"])

    @action(USE_CONSUMABLE)
    async def use_consumable(self, session, request):
        """Raise one curio's stats for good.

        ConsumableSelectWindow.onUseConsumable keeps the curio's old bonuses, reads the ones we
        answer with and shows the difference, so these must be the new TOTALS, never the deltas.
        """
        player, pet = self._pet(session, request)
        if pet is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        item_id = int(request.get(K.ITEM_ID, 0))
        quantity = max(1, int(request.get(K.ITEM_QTY, 1)))
        consumable = self.game.data.consumables.get(item_id)
        entry = next((item for item in player["inventory"]
                      if item["id"] == item_id and item["type"] == rewards.ITEM_CONSUMABLE), None)
        if consumable is None or entry is None or entry["qty"] < quantity:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        cost = consumable.use_gold * quantity
        if player["gold"] < cost:
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)

        species = self.game.data.species.get(pet["species"])
        matched = species is not None and species.type in consumable.bonus_types
        bonus = pet.setdefault("bonus", {})
        for stat, (normal, boosted) in consumable.stats.items():
            bonus[stat] = bonus.get(stat, 0) + (boosted if matched else normal) * quantity
        player["gold"] -= cost
        entry["qty"] -= quantity
        self.game.players.save(player)
        log.info("[%d] %dx %s no curio %d (%s)", session.id, quantity, consumable.name, pet["uid"],
                 "bonus do elemento" if matched else "valor normal")

        reply = (EsObject().set_integer(K.CHARACTER_GOLD, player["gold"])
                 .set_integer(K.PET_UID, pet["uid"])
                 .set_integer(K.ITEM_ID, item_id).set_integer(K.ITEM_QTY, quantity))
        for key, stat in (("PET_BONUS_HEALTH", "health"), ("PET_BONUS_DAMAGE", "damage"),
                          ("PET_BONUS_HEALING", "healing"), ("PET_BONUS_MANA", "mana"),
                          ("PET_BONUS_LUCK", "luck")):
            reply.set_integer(getattr(K, key), int(bonus.get(stat, 0)))
        return reply

    @action(RARITY_PROMOTE)
    async def rarity_promote(self, session, request):
        """Raise one curio a whole rarity, paying that rarity's shards and gold.

        onRarityPromoteComplete reads PET_ID, ITEM_QTY (the shard count LEFT, which it writes
        straight into the bag), PET_PROMOTED (a full curio, which REPLACES the one on screen)
        and CHARACTER_GOLD.  Shards are indexed by species id, as ShardBook builds them from
        PetBook rather than from a book of its own.
        """
        player, pet = self._pet(session, request)
        if pet is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        data = self.game.data
        species = data.species.get(pet["species"])
        if species is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        current = int(pet.get("rarity") or data.rarities.index(species.rarity))
        target = current + 1
        if target >= len(data.rarities):
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)   # already at the top
        shards_needed, gold_needed, _s, _g = data.rarity_promotion.get(target, (0, 0, 0, 0))
        if shards_needed <= 0:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)

        held = next((item for item in player["inventory"]
                     if item["id"] == species.id and item["type"] == rewards.ITEM_SHARD), None)
        if held is None or held["qty"] < shards_needed:
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)
        if player["gold"] < gold_needed:
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)

        held["qty"] -= shards_needed
        player["gold"] -= gold_needed
        pet["rarity"] = target
        self.game.players.save(player)
        log.info("[%d] curio %d promovido a %s por %d fragmentos e %d de ouro", session.id,
                 pet["uid"], data.rarities[target], shards_needed, gold_needed)
        return (EsObject().set_integer(K.PET_ID, species.id)
                .set_integer(K.ITEM_QTY, held["qty"])
                .set_esobject(K.PET_PROMOTED, players.pet_esobject(pet))
                .set_integer(K.CHARACTER_GOLD, player["gold"]))

    @action(RARITY_SUMMON)
    async def rarity_summon(self, session, request):
        """Summon a brand new curio of a species out of its shards.

        onRaritySummonComplete reads PET_ID, PET_UID (the newcomer), ITEM_QTY (shards left),
        CHARACTER_GOLD and CHARACTER_PETS - and that last one is an EsObject ARRAY holding the
        WHOLE collection, which it assigns over character.pets, so it must not be a partial list.
        """
        player = session.data.get("player")
        if player is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        data = self.game.data
        species = data.species.get(int(request.get(K.PET_ID, 0)))
        if species is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        rarity_index = data.rarities.index(species.rarity) if species.rarity in data.rarities else 0
        _ps, _pg, shards_needed, gold_needed = data.rarity_promotion.get(rarity_index, (0, 0, 0, 0))
        if shards_needed <= 0:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)

        held = next((item for item in player["inventory"]
                     if item["id"] == species.id and item["type"] == rewards.ITEM_SHARD), None)
        if held is None or held["qty"] < shards_needed:
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)
        if player["gold"] < gold_needed:
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)

        held["qty"] -= shards_needed
        player["gold"] -= gold_needed
        novo = players.add_pet(player, data, species.id)
        self.game.players.save(player)
        log.info("[%d] invocou %s (uid %d) por %d fragmentos e %d de ouro", session.id,
                 species.name, novo["uid"], shards_needed, gold_needed)
        return (EsObject().set_integer(K.PET_ID, species.id)
                .set_integer(K.PET_UID, novo["uid"])
                .set_integer(K.ITEM_QTY, held["qty"])
                .set_integer(K.CHARACTER_GOLD, player["gold"])
                .set_esobject_array(K.CHARACTER_PETS,
                                    [players.pet_esobject(p) for p in player["pets"]]))

    @action(FUSION)
    async def fusion(self, session, request):
        """Fuse duplicates of a curio into it, raising its fusion level.

        PetFusionWindow collects exactly upgradeDupes duplicates (its loop runs to that number).
        doFusion sends the keeper as an INTEGER in PET_UID and the duplicates as an INTEGER ARRAY
        in CHARACTER_PETS - the same key the reply uses to name the uids the client must drop.
        onFusion then reads PET_UID, PET_FUSION and that array back.
        """
        player = session.data.get("player")
        if player is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        keeper_uid = int(request.get(K.PET_UID, 0))
        uids = [int(u) for u in (request.get(K.CHARACTER_PETS) or [])]
        keeper = next((p for p in player["pets"] if p["uid"] == keeper_uid), None)
        if keeper is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)

        step = self.game.data.fusion_steps.get(keeper["fusion"], (-1, -1))
        needed, becomes = step
        if needed <= 0 or becomes < 0:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        on_team = {uid for team in player["teams"] for uid in team["pet_uids"]}
        dupes = [p for p in player["pets"]
                 if p["uid"] in uids and p["uid"] != keeper["uid"]
                 and p["species"] == keeper["species"] and p["uid"] not in on_team]
        if len(dupes) < needed:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)

        spent = dupes[:needed]
        gone = [p["uid"] for p in spent]
        player["pets"] = [p for p in player["pets"] if p["uid"] not in gone]
        keeper["fusion"] = becomes
        self.game.players.save(player)
        log.info("[%d] curio %d fundido para fusao %d consumindo %s", session.id,
                 keeper["uid"], becomes, gone)
        return (EsObject().set_integer(K.PET_UID, keeper["uid"])
                .set_integer(K.PET_FUSION, keeper["fusion"])
                .set_integer_array(K.CHARACTER_PETS, gone))

    @action(USE_ENCHANT)
    async def use_enchant(self, session, request):
        """Slot an enchant into one of the curio's three coloured sockets.

        EnchantSelectWindow.onUseEnchant reads PET_UID, then whichever PET_<COLOUR>_ENCHANT keys
        are present, and finally removes ITEM_QTY of ENCHANT_ID from the bag.  Anything already
        in the socket is destroyed, which is what the client's confirmation warns about.
        """
        player, pet = self._pet(session, request)
        if pet is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        enchant = self.game.data.enchants.get(int(request.get(K.ENCHANT_ID, 0)))
        slot = int(request.get(K.ENCHANT_SLOT, 0))
        if enchant is None or slot not in SLOT_KEYS or slot not in enchant.slots:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        entry = next((item for item in player["inventory"]
                      if item["id"] == enchant.id and item["type"] == rewards.ITEM_ENCHANT), None)
        if entry is None or entry["qty"] < 1:
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)

        entry["qty"] -= 1
        pet.setdefault("enchants", {})[str(slot)] = enchant.id
        self.game.players.save(player)
        log.info("[%d] encantou o curio %d com %s no slot %d", session.id, pet["uid"], enchant.name, slot)
        return (EsObject().set_integer(K.PET_UID, pet["uid"])
                .set_integer(getattr(K, SLOT_KEYS[slot]), enchant.id)
                .set_integer(K.ENCHANT_ID, enchant.id)
                .set_integer(K.ITEM_QTY, 1))

    @action(REMOVE_ENCHANT)
    async def remove_enchant(self, session, request):
        """Empty a socket.  PetEnchantOptionsWindow reads the same colour keys back."""
        player, pet = self._pet(session, request)
        slot = int(request.get(K.ENCHANT_SLOT, 0))
        if pet is None or slot not in SLOT_KEYS:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        pet.setdefault("enchants", {}).pop(str(slot), None)
        self.game.players.save(player)
        return (EsObject().set_integer(K.PET_UID, pet["uid"])
                .set_integer(getattr(K, SLOT_KEYS[slot]), 0))

    @action(UPGRADE_ENCHANT)
    async def upgrade_enchant(self, session, request):
        """Promote the enchant sitting in a socket to its next tier, paying its upgradeGold."""
        player, pet = self._pet(session, request)
        slot = int(request.get(K.ENCHANT_SLOT, 0))
        if pet is None or slot not in SLOT_KEYS:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        current = self.game.data.enchants.get(int((pet.get("enchants") or {}).get(str(slot), 0)))
        better = self.game.data.upgrade_of(current.id) if current else None
        if current is None or better is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        if player["gold"] < current.upgrade_gold:
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)

        player["gold"] -= current.upgrade_gold
        pet["enchants"][str(slot)] = better.id
        self.game.players.save(player)
        log.info("[%d] %s virou %s no curio %d", session.id, current.name, better.name, pet["uid"])
        return (EsObject().set_integer(K.PET_UID, pet["uid"])
                .set_integer(getattr(K, SLOT_KEYS[slot]), better.id)
                .set_integer(K.CHARACTER_GOLD, player["gold"]))

    @action(UPGRADE_SKILL)
    async def upgrade_skill(self, session, request):
        player, pet = self._pet(session, request)
        species = self.game.data.species.get(pet["species"]) if pet else None
        skill_id = int(request.get(K.PET_SKILL_ID, 0))
        skill = next((s for s in species.skills if s.id == skill_id), None) if species else None
        if skill is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        ranks = pet["skill_ranks"]
        while len(ranks) <= skill_id:
            ranks.append(0)
        rank = ranks[skill_id]
        error = self._upgrade_error(pet, skill, rank)
        if error:
            return EsObject().set_integer(K.ACTION_ERROR, error)
        pet["skill_points"] -= skill.rank_costs[rank]
        ranks[skill_id] = rank + 1
        if rank == 0:
            self._equip(pet, skill_id)
        log.info("[%d] curio %s subiu %s para o rank %d", session.id, species.name, skill.name, rank + 1)
        self.game.players.save(player)
        return (EsObject().set_integer(K.PET_SKILL_POINTS, pet["skill_points"])
                .set_integer_array(K.PET_SKILL_RANKS, ranks)
                .set_integer_array(K.PET_SKILL_SLOTS, pet["skill_slots"]))

    @action(PRESTIGE)
    async def prestige(self, session, request):
        """Evolve: only at the level cap of the current evolution, paid in gold by rarity."""
        player, pet = self._pet(session, request)
        data = self.game.data
        species = data.species.get(pet["species"]) if pet else None
        if species is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        following = pet["prestige"] + 1
        if following >= len(species.prestiges) or pet["level"] < data.max_level(species, pet["prestige"]):
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        cost = data.rarity_costs.get(species.rarity, {}).get(following, 0)
        if cost > player["gold"]:
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)
        player["gold"] -= cost
        pet["prestige"] = following
        pet["skin"] = following          # the evolved look; PetSkinWindow offers 0..prestige
        progress.bump(player, "evolves", 1)
        log.info("[%d] curio %s evoluiu para a forma %d", session.id, species.name, following)
        self.game.push_progress(session, player, progress.advance_jobs(player, data, "upgrade", target="pet"))
        self.game.players.save(player)
        return (EsObject().set_integer(K.CHARACTER_GOLD, player["gold"])
                .set_integer(K.PET_UID, pet["uid"]).set_integer(K.PET_PRESTIGE, pet["prestige"])
                .set_integer(K.PET_SKIN, pet["skin"]).set_integer(K.PET_LEVEL, pet["level"])
                .set_integer(K.PET_EXP, pet["exp"]).set_integer(K.PET_SKILL_POINTS, pet["skill_points"])
                .set_integer_array(K.PET_SKILL_RANKS, pet["skill_ranks"])
                .set_integer_array(K.PET_SKILL_SLOTS, pet["skill_slots"])
                .set_number(K.CHARACTER_UPGRADE_MILLISECONDS, 0.0))

    @action(UPGRADE_RANK)
    async def upgrade_rank(self, session, request):
        """Rank up, paid with the stardust the rank book puts on the curio's current rank."""
        player, pet = self._pet(session, request)
        if pet is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        item_id, item_type, quantity, following = self.game.data.rank_upgrades.get(pet["rank"], (-1, "", 0, -1))
        if following < 0 or quantity <= 0:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)       # already the top rank
        field = rewards.CURRENCY_FIELDS.get(item_id) if item_type == "currency" else None
        if field is None or player.get(field, 0) < quantity:
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)
        player[field] -= quantity
        pet["rank"] = following
        progress.bump(player, "rankups", 1)
        log.info("[%d] curio subiu para o rank %d", session.id, following)
        self.game.push_progress(session, player,
                                progress.advance_jobs(player, self.game.data, "upgrade", target="pet"))
        self.game.players.save(player)
        # the client takes exactly this item off the player when it reads the reply
        return (EsObject().set_integer(K.PET_RANK, pet["rank"]).set_integer(K.ITEM_ID, item_id)
                .set_integer(K.ITEM_TYPE, rewards.type_id(item_type)).set_integer(K.ITEM_QTY, quantity)
                .set_number(K.CHARACTER_UPGRADE_MILLISECONDS, 0.0))

    @action(SAVE_SKIN)
    async def save_skin(self, session, request):
        player, pet = self._pet(session, request)
        if pet is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        skin = int(request.get(K.PET_SKIN, 0))
        # PetSkinWindow.getSkinIDs builds a SIGNED list: it pushes -0, -1 ... -prestige for the
        # curio's own evolution looks, then the positive id of every SkinBook entry whose petID
        # matches the species.  The old check (0..prestige) rejected both, so an evolved curio
        # could not even pick its own evolved look.  There is no inventory gate in that window:
        # authoring a skin for a species is what makes it selectable, exactly as the client does.
        prestige_look = -pet["prestige"] <= skin <= 0
        skin_ref = self.game.data.skins.get(skin) if skin > 0 else None
        if not prestige_look and (skin_ref is None or skin_ref.pet_id != pet["species"]):
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        pet["skin"] = skin
        self.game.players.save(player)
        return EsObject().set_integer(K.PET_SKIN, skin)

    @action(SAVE_TEAM)
    async def save_team(self, session, request):
        player = session.data.get("player")
        team = self._team(player, request)
        if team is None:
            return None
        owned = {pet["uid"] for pet in player["pets"]}
        team["pet_uids"] = [uid for uid in (request.get(K.TEAM_PET_UIDS) or []) if uid in owned]
        self.game.players.save(player)
        return None

    @action(SAVE_TEAM_NAME)
    async def save_team_name(self, session, request):
        player = session.data.get("player")
        team = self._team(player, request)
        if team is None:
            return None
        team["name"] = (request.get(K.TEAM_NAME) or "").strip()[:NAME_MAX_LENGTH]
        self.game.players.save(player)
        return None

    @action(SAVE_SKILL_SLOTS)
    async def save_skill_slots(self, session, request):
        player, pet = self._pet(session, request)
        if pet is None:
            return None
        ranks = pet["skill_ranks"]
        wanted = [int(slot) for slot in (request.get(K.PET_SKILL_SLOTS) or [])]
        # only a skill the curio actually learned may sit in a slot; 0 is an empty slot
        slots = [sid if 0 < sid < len(ranks) and ranks[sid] > 0 else 0 for sid in wanted]
        count = len(pet["skill_slots"]) or len(slots)
        pet["skill_slots"] = (slots + [0] * count)[:count]
        self.game.players.save(player)
        return None

    @action(USE_EXP)
    async def use_exp(self, session, request):
        """Spend the player's own experience on curios, the way the victory screen and the curio
        window do: each entry says how much to pour into one curio."""
        player = session.data.get("player")
        if player is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        data = self.game.data
        updated, levels = [], 0
        for wanted in (request.get(K.CHARACTER_PETS) or []):
            uid = int(wanted.get(K.PET_UID, 0))
            pet = next((p for p in player["pets"] if p["uid"] == uid), None)
            species = data.species.get(pet["species"]) if pet else None
            if pet is None or species is None:
                return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
            amount = min(max(0, int(wanted.get(K.PET_EXP, 0))), player["exp"])
            if amount <= 0:
                continue
            player["exp"] -= amount
            levels += players.grant_exp(pet, species, data, amount)
            updated.append(EsObject().set_integer(K.PET_UID, pet["uid"]).set_integer(K.PET_EXP, pet["exp"])
                           .set_integer(K.PET_LEVEL, pet["level"])
                           .set_integer(K.PET_SKILL_POINTS, pet["skill_points"]))
        if not updated:
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)
        log.info("[%d] gastou experiencia em %d curio(s), %d nivel(is)", session.id, len(updated), levels)
        moved = progress.advance_jobs(player, data, "level", levels, target="pet") if levels else []
        self.game.push_progress(session, player, moved)
        self.game.players.save(player)
        return (EsObject().set_integer(K.CHARACTER_EXP, player["exp"])
                .set_esobject_array(K.CHARACTER_PETS, updated))

    @action(EXCHANGE_PETS_CORES)
    async def exchange_pets(self, session, request):
        """Trade curios away for character experience, the way PetExchangeWindow previews it."""
        player = session.data.get("player")
        if player is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
        data = self.game.data
        wanted = {int(uid) for uid in (request.get(K.PET_UID) or [])}
        chosen = [pet for pet in player["pets"] if pet["uid"] in wanted]
        if not chosen or len(chosen) >= len(player["pets"]):
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)   # never trade the last curio away
        on_a_team = {uid for team in player["teams"] for uid in team["pet_uids"]}
        gained = 0
        cores = [0, 0, 0]        # epic, legendary, mythic pieces this exchange is worth
        for pet in chosen:
            species = data.species.get(pet["species"])
            if species is None or species.starter:
                return EsObject().set_integer(K.ACTION_ERROR, INVALID_PET)
            if pet["uid"] in on_a_team:
                return EsObject().set_integer(K.ACTION_ERROR, PET_ON_OFFENSE_TEAM)
            gained += self._exchange_value(data, species, pet)
            for index, pieces in enumerate(data.rarity_cores.get(species.rarity, (0, 0, 0))):
                cores[index] += pieces
        player["exp"] += gained
        player["pets"] = [pet for pet in player["pets"] if pet["uid"] not in wanted]
        # the pieces are materials 48/49/50 - ids the client hard-codes as the core fragments -
        # so they live in the bag like anything else, and the reply also states the new totals
        # because PetExchangeWindow prints them straight from EPIC/LEGENDARY/MYTHIC_CORE_PIECES.
        for material_id, earned in zip(CORE_MATERIALS, cores):
            if earned:
                rewards.give(player, data, material_id, rewards.ITEM_MATERIAL, earned)
        progress.bump(player, "exchanges", len(chosen))
        log.info("[%d] trocou %d curio(s) por %d de experiencia e nucleos %s",
                 session.id, len(chosen), gained, cores)
        self.game.push_progress(session, player)
        self.game.players.save(player)
        reply = (EsObject().set_integer(K.CHARACTER_EXP, player["exp"])
                 .set_integer_array(K.PET_UID, [pet["uid"] for pet in chosen]))
        for key, material_id in zip(("EPIC_CORE_PIECES", "LEGENDARY_CORE_PIECES", "MYTHIC_CORE_PIECES"),
                                    CORE_MATERIALS):
            held = next((item for item in player["inventory"]
                         if item["id"] == material_id and item["type"] == rewards.ITEM_MATERIAL), None)
            reply.set_integer(getattr(K, key), held["qty"] if held else 0)
        return reply

    @staticmethod
    def _exchange_value(data, species, pet):
        """The rarity's base plus the experience already banked, counting every evolution passed."""
        base, mult = data.rarity_exchange.get(species.rarity, (0, 1.0))
        banked = pet["exp"]
        for prestige in species.prestiges:
            if prestige.id < pet["prestige"]:
                banked += exp_for_level(prestige.max_level, species.size)
        return int(base + banked * mult)

    @action(PETS_COLLECTED)
    async def pets_collected(self, session, request):
        return None

    # ---------------------------------------------------------------- helpers
    def _upgrade_error(self, pet, skill, rank):
        """The same gates as model.pet.PetData.skillIsUpgradable, as an error code (0 = allowed).
        A skill the tree still has locked is a different answer from one the curio cannot pay for."""
        if rank >= len(skill.rank_costs):                       # skillIsMaxed
            return INVALID_PET
        if skill.level_req > pet["level"]:                      # skillIsLocked, by level
            return INVALID_PET
        ranks = pet["skill_ranks"]
        for required in skill.skills_req:                       # skillIsLocked, by prerequisite
            if required >= len(ranks) or ranks[required] <= 0:
                return INVALID_PET
        if len(self.game.data.skills.get(skill.link, [])) < rank + 1:
            return INVALID_PET                                  # the next rank has no ability
        return 0 if skill.rank_costs[rank] <= pet["skill_points"] else INSUFFICIENT_FUNDS

    @staticmethod
    def _equip(pet, skill_id):
        """A newly learned skill takes the first empty slot, which is why the reply carries them."""
        slots = pet["skill_slots"]
        if skill_id in slots:
            return
        for index, value in enumerate(slots):
            if value == 0:
                slots[index] = skill_id
                return

    @staticmethod
    def _pet(session, request):
        player = session.data.get("player")
        if player is None:
            return None, None
        uid = int(request.get(K.PET_UID, 0))
        return player, next((pet for pet in player["pets"] if pet["uid"] == uid), None)

    @staticmethod
    def _team(player, request):
        if player is None:
            return None
        team_id = int(request.get(K.TEAM_ID, 0))
        team = next((t for t in player["teams"] if t["id"] == team_id), None)
        if team is None:
            team = {"id": team_id, "name": "", "pet_uids": []}
            player["teams"].append(team)
        return team
