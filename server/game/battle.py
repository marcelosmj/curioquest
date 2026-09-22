"""Node battles.

The client only animates what it is told, so the whole fight happens here: damage, healing,
buffs, cooldowns, the enemy's turns and the rewards. Every step is sent as one message in a
MESSAGE_LIST, in the order plugins.BattlePlugin expects to play them.
"""
import logging
import os
import random

from ..es5.esobject import EsObject
from .keys import K
from .player import grant_exp, pet_esobject

log = logging.getLogger("battle")

# action ids of plugins.BattlePlugin
SELECT_PET, CURRENT_PLAYER, HEALTH_CHANGE, MANA_CHANGE, COMPLETE = 2, 3, 4, 5, 6
SKILL, FX, RESULTS, BUFF_ADD, BUFF_REMOVE, DEFEND, CONCEDE = 7, 8, 9, 10, 11, 12, 13
ABILITY, MISS, COOLDOWNS, SKILL_DISABLE, AUTO_PLAY, PET_REMOVE, PET_ADD = 14, 15, 16, 17, 18, 19, 20

SHARD_DROP_CHANCE = 35        # percent, per won fight, for a shard of the curio defeated
TYPE_NODE = 1                 # ui.battle.BattleScreen.TYPE_NODE
MISS_CHANCE = 0.04
CRIT_MULTIPLIER = 1.5
DEFEND_REDUCTION = 0.5
MANA_PER_TURN = 1
CRIT_PER_LUCK = 0.2           # luck points per 1% critical chance
MAX_CRIT_CHANCE = 0.35
STUNNING = ("stun", "sleep")  # effects that stop a curio from acting


class ActiveBuff:
    """A buff on a curio, with the damage of whoever applied it (for damage over time)."""

    def __init__(self, index, buff, duration, source_damage):
        self.index, self.buff, self.duration, self.source_damage = index, buff, duration, source_damage

    def esobject(self):
        return (EsObject().set_integer(K.BATTLE_PET_BUFF_INDEX, self.index)
                .set_integer(K.BATTLE_PET_BUFF_ID, self.buff.id)
                .set_integer(K.BATTLE_PET_BUFF_DURATION, self.duration))


class BattlePet:
    def __init__(self, data, index, species, level, prestige=0, rank=0, fusion=0, uid=0, name="",
                 skill_ranks=None, skill_slots=None, bonus=None):
        self.index, self.species, self.level = index, species, level
        self.prestige, self.rank, self.fusion = prestige, rank, fusion
        self.uid, self.name = uid, name
        self.skill_ranks = list(skill_ranks) if skill_ranks else self._default_ranks()
        self.skill_slots = list(skill_slots) if skill_slots else self._default_slots(data)
        # consumable bonuses sit OUTSIDE data.stat on purpose: that function is the client's own
        # formula, and the client adds PET_BONUS_* on top of it the same way
        gain = bonus or {}
        self.max_health = max(1, data.stat(species, "health", level, prestige, rank, fusion) + gain.get("health", 0))
        self.max_mana = max(1, data.stat(species, "mana", level, prestige, rank, fusion) + gain.get("mana", 0))
        self.damage = max(1, data.stat(species, "damage", level, prestige, rank, fusion) + gain.get("damage", 0))
        self.healing = max(1, data.stat(species, "healing", level, prestige, rank, fusion) + gain.get("healing", 0))
        self.luck = max(0, data.stat(species, "luck", level, prestige, rank, fusion) + gain.get("luck", 0))
        self.health, self.mana = self.max_health, self.max_mana
        self.defending = False
        self.cooldowns = [0] * len(self.skill_ranks)
        self.buffs = []
        self._next_buff_index = 0

    def _default_ranks(self):
        """A wild curio knows what its level allows, at a rank that grows with the level."""
        ranks = [0] * (max([skill.id for skill in self.species.skills], default=0) + 1)
        for skill in self.species.skills:
            if skill.level_req <= self.level:
                ranks[skill.id] = max(skill.start_rank, min(len(skill.rank_costs), 1 + self.level // 10))
        return ranks

    def _default_slots(self, data):
        known = [skill.id for skill in self.species.skills if self.skill_ranks[skill.id] > 0]
        slots = data.var("skillSlots", 4)
        return (known[:slots] + [0] * slots)[:slots]

    @property
    def is_dead(self):
        return self.health <= 0

    @property
    def element(self):
        return self.species.type

    def has_effect(self, *types):
        return any(effect.type in types for active in self.buffs for effect in active.buff.effects)

    def effect_amount(self, effect_type):
        return sum(effect.amount for active in self.buffs for effect in active.buff.effects
                   if effect.type == effect_type)

    def add_buff(self, buff, duration, source_damage):
        active = ActiveBuff(self._next_buff_index, buff, duration, source_damage)
        self._next_buff_index += 1
        self.buffs.append(active)
        return active

    def abilities(self, data):
        """(pet skill, ability) for every skill the curio has equipped and can use."""
        out = []
        for skill_id in self.skill_slots:
            skill = next((s for s in self.species.skills if s.id == skill_id), None)
            rank = self.skill_ranks[skill_id] if skill_id < len(self.skill_ranks) else 0
            if not skill or rank <= 0:
                continue
            ranks = data.skills.get(skill.link, [])
            if rank <= len(ranks):
                out.append((skill, ranks[rank - 1]))
        return out

    def save_dict(self):
        return {"uid": self.uid, "species": self.species.id, "name": self.name, "prestige": self.prestige,
                "rank": self.rank, "fusion": self.fusion, "level": self.level, "exp": 0, "skin": 0,
                "skill_points": 0, "fatigue": 0, "skill_ranks": self.skill_ranks, "skill_slots": self.skill_slots}

    def esobject(self):
        eso = pet_esobject(self.save_dict())
        eso.set_integer(K.BATTLE_PET_INDEX, self.index)
        eso.set_integer(K.BATTLE_PET_TOTAL_HEALTH, self.max_health)
        eso.set_integer(K.BATTLE_PET_CURRENT_HEALTH, max(0, self.health))
        eso.set_integer(K.BATTLE_PET_TOTAL_MANA, self.max_mana)
        eso.set_integer(K.BATTLE_PET_CURRENT_MANA, max(0, self.mana))
        eso.set_boolean(K.BATTLE_PET_DEFENDING, self.defending)
        eso.set_esobject_array(K.BATTLE_PET_BUFFS, [active.esobject() for active in self.buffs])
        eso.set_integer_array(K.BATTLE_PET_COOLDOWNS, self.cooldowns)
        return eso


class BattlePlayer:
    def __init__(self, index, player_id, user_name, name, pets, is_ai=False):
        self.index, self.player_id, self.user_name, self.name = index, player_id, user_name, name
        self.pets, self.is_ai = pets, is_ai
        self.current = pets[0] if pets else None

    @property
    def alive_pets(self):
        return [pet for pet in self.pets if not pet.is_dead]

    def esobject(self):
        return (EsObject().set_integer(K.BATTLE_PLAYER_INDEX, self.index)
                .set_string(K.CHARACTER_PLAYER_ID, self.player_id)
                .set_string(K.CHARACTER_USERNAME, self.user_name)
                .set_string(K.CHARACTER_NAME, self.name)
                .set_integer(K.BATTLE_CURRENT_PET_INDEX, -1)
                .set_esobject_array(K.BATTLE_PETS, [pet.esobject() for pet in self.pets]))


class Battle:
    """One node battle. `messages` collects what the client has to animate next."""

    def __init__(self, game, player, node, battle_ref, battle_index, room_id, zone_id):
        self.game, self.data = game, game.data
        self.player_save = player
        self.node, self.battle_ref, self.battle_index = node, battle_ref, battle_index
        self.room_id, self.zone_id = room_id, zone_id
        self.messages = []
        self.finished = False
        self.won = False
        self.rewards = {}
        self.players = [self._player_side(player), self._enemy_side(battle_ref)]
        # what the player did in this fight, for the jobs and the achievements
        self.stats = {"damage": 0, "crits": 0, "healing": 0, "damage_by_element": {}, "level_ups": 0}
        self.current = self.players[0]

    # ---------------------------------------------------------------- setup
    def _player_side(self, player):
        team = next((team for team in player["teams"] if team["id"] == player["offense_team"]), None)
        uids = team["pet_uids"] if team else []
        pets, index = [], 0
        for uid in uids:
            saved = next((pet for pet in player["pets"] if pet["uid"] == uid), None)
            species = self.data.species.get(saved["species"]) if saved else None
            if not species:
                continue
            pets.append(BattlePet(self.data, index, species, saved["level"], saved["prestige"], saved["rank"],
                                  saved["fusion"], saved["uid"], saved["name"], saved["skill_ranks"],
                                  saved["skill_slots"], self._pet_bonus(saved)))
            index += 1
        name = player["name"] or "Player"
        return BattlePlayer(0, player["player_id"], name, name, pets)

    def _pet_bonus(self, saved):
        """Consumable gains plus whatever the curio's enchants add, as one flat stat dict."""
        total = dict(saved.get("bonus") or {})
        for _slot, enchant_id in (saved.get("enchants") or {}).items():
            enchant = self.data.enchants.get(int(enchant_id or 0))
            if enchant:
                for stat, amount in enchant.stats.items():
                    total[stat] = total.get(stat, 0) + amount
        return total

    def _enemy_side(self, battle_ref):
        pets = []
        for index, (species_id, level) in enumerate(battle_ref.pets):
            species = self.data.species.get(species_id)
            if species:
                pets.append(BattlePet(self.data, index, species, max(1, level)))
        return BattlePlayer(1, "", "", battle_ref.name or "Enemy", pets, is_ai=True)

    def enter_payload(self):
        # CQ_BATTLE_MIN=1 manda a versao enxuta do ENTER_BATTLE (um curio por lado, sem buffs nem
        # cooldowns): e a bisseccao que isola qual parte do payload o cliente real recusa
        if os.environ.get("CQ_BATTLE_MIN"):
            return self._minimal_payload()
        return (EsObject().set_integer(K.ROOM_ID, self.room_id)
                .set_integer(K.ROOM_ZONE_ID, self.zone_id)
                .set_integer(K.BATTLE_TYPE, TYPE_NODE)
                .set_integer(K.BATTLE_CURRENT_PLAYER_INDEX, self.current.index)
                .set_esobject_array(K.BATTLE_PLAYERS, [side.esobject() for side in self.players])
                .set_integer(K.ZONE_ID, self.node.zone_id)
                .set_integer(K.ZONE_DIFFICULTY, self.node.difficulty)
                .set_integer(K.ZONE_NODE_ID, self.node.id)
                .set_integer(K.ZONE_NODE_BATTLE_INDEX, self.battle_index))

    def _minimal_payload(self):
        """The same ENTER_BATTLE with everything optional stripped: no buffs, no cooldowns and a
        single curio per side.  If the battle screen opens with this, the offending field is in
        what was left out; if it still hangs, the fault is in the bare skeleton."""
        sides = []
        for side in self.players:
            pet = side.pets[0]
            enxuto = pet_esobject(pet.save_dict())
            enxuto.set_integer(K.BATTLE_PET_INDEX, pet.index)
            enxuto.set_integer(K.BATTLE_PET_TOTAL_HEALTH, pet.max_health)
            enxuto.set_integer(K.BATTLE_PET_CURRENT_HEALTH, max(0, pet.health))
            enxuto.set_integer(K.BATTLE_PET_TOTAL_MANA, pet.max_mana)
            enxuto.set_integer(K.BATTLE_PET_CURRENT_MANA, max(0, pet.mana))
            enxuto.set_boolean(K.BATTLE_PET_DEFENDING, False)
            sides.append(EsObject().set_integer(K.BATTLE_PLAYER_INDEX, side.index)
                         .set_string(K.CHARACTER_PLAYER_ID, side.player_id)
                         .set_string(K.CHARACTER_USERNAME, side.user_name)
                         .set_string(K.CHARACTER_NAME, side.name)
                         .set_integer(K.BATTLE_CURRENT_PET_INDEX, -1)
                         .set_esobject_array(K.BATTLE_PETS, [enxuto]))
        log.info("ENTER_BATTLE enxuto (CQ_BATTLE_MIN): %d lados, 1 curio cada", len(sides))
        return (EsObject().set_integer(K.ROOM_ID, self.room_id)
                .set_integer(K.ROOM_ZONE_ID, self.zone_id)
                .set_integer(K.BATTLE_TYPE, TYPE_NODE)
                .set_integer(K.BATTLE_CURRENT_PLAYER_INDEX, 0)
                .set_esobject_array(K.BATTLE_PLAYERS, sides)
                .set_integer(K.ZONE_ID, self.node.zone_id)
                .set_integer(K.ZONE_DIFFICULTY, self.node.difficulty)
                .set_integer(K.ZONE_NODE_ID, self.node.id)
                .set_integer(K.ZONE_NODE_BATTLE_INDEX, self.battle_index))

    # ---------------------------------------------------------------- messages
    def _message(self, action, **fields):
        eso = EsObject().set_integer(K.ACTION_TYPE, action)
        for key, value in fields.items():
            setter = {int: eso.set_integer, bool: eso.set_boolean, str: eso.set_string}.get(type(value))
            if setter:
                setter(getattr(K, key), value)
            elif isinstance(value, list):
                eso.set_integer_array(getattr(K, key), value)
            elif isinstance(value, EsObject):
                eso.set_esobject(getattr(K, key), value)
        self.messages.append(eso)
        return eso

    def take_messages(self):
        messages, self.messages = self.messages, []
        return messages

    def opponent(self, side):
        return self.players[1 - side.index]

    # ---------------------------------------------------------------- turns
    def start(self):
        """First turn: bring out starting curios, then begin first turn."""
        for side in self.players:
            if side.current:
                self._message(SELECT_PET, BATTLE_PLAYER_INDEX=side.index, BATTLE_CURRENT_PET_INDEX=side.current.index)
        self._begin_turn(self.current)

    def _begin_turn(self, side):
        self._message(CURRENT_PLAYER, BATTLE_CURRENT_PLAYER_INDEX=side.index)
        for pet in side.alive_pets:
            self._tick_buffs(side, pet)
            if pet.cooldowns and any(pet.cooldowns):
                pet.cooldowns = [max(0, value - 1) for value in pet.cooldowns]
                self._message(COOLDOWNS, BATTLE_PLAYER_INDEX=side.index, BATTLE_PET_INDEX=pet.index,
                              BATTLE_PET_COOLDOWNS=pet.cooldowns)
        if side.current and not side.current.is_dead:
            side.current.defending = False
            self._change_mana(side, side.current, MANA_PER_TURN)
        if self.finished:
            return
        if side.is_ai:
            self._ai_turn(side)

    def _tick_buffs(self, side, pet):
        for active in list(pet.buffs):
            for trigger in active.buff.triggers:
                if trigger.type == "turnstart":
                    for action in trigger.actions:
                        self._apply_action(side, pet, side, pet, action, active.source_damage)
            active.duration -= 1
            if active.duration <= 0:
                pet.buffs.remove(active)
                self._message(BUFF_REMOVE, BATTLE_PLAYER_INDEX=side.index, BATTLE_PET_INDEX=pet.index,
                              BATTLE_PET_BUFF_INDEX=active.index)

    def _end_turn(self):
        if self.finished:
            return
        self.current = self.opponent(self.current)
        self._begin_turn(self.current)

    # ---------------------------------------------------------------- player actions
    def handle(self, request):
        action = request.get(K.ACTION_TYPE)
        if self.finished:
            return
        if action == SKILL:
            self._use_skill(self.players[0], request)
        elif action == DEFEND:
            self._defend(self.players[0])
        elif action == SELECT_PET:
            self._select_pet(self.players[0], int(request.get(K.BATTLE_PET_INDEX, 0)), end_turn=True)
        elif action == CONCEDE:
            self._message(CONCEDE, BATTLE_PLAYER_INDEX=0)
            self._finish(self.players[1])
        elif action == AUTO_PLAY:
            self._ai_turn(self.players[0])
        else:
            log.warning("acao de batalha nao tratada: %s", action)

    def _use_skill(self, side, request):
        pet = side.current
        if not pet or pet.is_dead:
            return
        skill_id = int(request.get(K.BATTLE_SKILL_ID, 0))
        pair = next((item for item in pet.abilities(self.data) if item[0].id == skill_id), None)
        if not pair:
            log.warning("curio %s nao tem a skill %s equipada", pet.species.name, skill_id)
            return
        skill, ability = pair
        target = None
        if request.has(K.BATTLE_TARGET_PET_INDEX):
            target_side = self.players[int(request.get(K.BATTLE_TARGET_PLAYER_INDEX, 0))]
            target = next((p for p in target_side.pets if p.index == int(request.get(K.BATTLE_TARGET_PET_INDEX))), None)
        self._resolve_ability(side, pet, skill, ability, target)

    def _defend(self, side):
        pet = side.current
        if not pet or pet.is_dead:
            return
        pet.defending = True
        self._message(DEFEND, BATTLE_PLAYER_INDEX=side.index, BATTLE_PET_INDEX=pet.index,
                      BATTLE_PET_DEFENDING=True)
        self._end_turn()

    def _select_pet(self, side, index, end_turn):
        pet = next((p for p in side.pets if p.index == index and not p.is_dead), None)
        if not pet:
            return
        side.current = pet
        self._message(SELECT_PET, BATTLE_PLAYER_INDEX=side.index, BATTLE_CURRENT_PET_INDEX=pet.index)
        if end_turn:
            self._end_turn()

    # ---------------------------------------------------------------- resolution
    def _resolve_ability(self, side, pet, skill, ability, target):
        if pet.mana < ability.mana_cost:
            return
        pet.mana -= ability.mana_cost
        if ability.mana_cost:
            self._message(MANA_CHANGE, BATTLE_PLAYER_INDEX=side.index, BATTLE_PET_INDEX=pet.index,
                          BATTLE_PET_CURRENT_MANA=pet.mana, BATTLE_MANA_CHANGE=-ability.mana_cost,
                          BATTLE_EFFECT_MODIFIER=0, BATTLE_EFFECT_TYPE=self._type_id(pet.element))
        if ability.cooldown:
            pet.cooldowns[skill.id] = ability.cooldown + 1
        self._message(ABILITY, BATTLE_PLAYER_INDEX=side.index, BATTLE_PET_INDEX=pet.index,
                      BATTLE_SKILL_ID=skill.id, BATTLE_ABILITY_INDEX=ability.rank,
                      BATTLE_PET_COOLDOWNS=pet.cooldowns)
        if pet.has_effect(*STUNNING):
            self._end_turn()
            return
        for action in ability.actions:
            for victim_side, victim in self._targets(side, pet, action, target):
                self._apply_action(side, pet, victim_side, victim, action, pet.damage)
        self._check_dead()
        if not self.finished:
            self._end_turn()

    def _targets(self, side, pet, action, chosen):
        enemy = self.opponent(side)
        target = action.target or "enemy"
        if target == "self":
            return [(side, pet)]
        if target == "enemy":
            return [(enemy, enemy.current)] if enemy.current and not enemy.current.is_dead else []
        if target == "enemyteam":
            return [(enemy, victim) for victim in enemy.alive_pets]
        if target == "selfteam":
            return [(side, friend) for friend in side.alive_pets]
        if target == "selfteamothers":
            return [(side, friend) for friend in side.alive_pets if friend is not pet]
        if target in ("select", "selectteam"):
            if chosen is None:
                return [(enemy, enemy.current)] if enemy.current else []
            owner = self.players[0] if chosen in self.players[0].pets else self.players[1]
            return [(owner, chosen)]
        if target == "all":
            return [(owner, victim) for owner in self.players for victim in owner.alive_pets]
        return [(enemy, enemy.current)] if enemy.current else []

    def _apply_action(self, side, pet, victim_side, victim, action, source_damage):
        if victim is None:
            return
        if action.type in ("healthdamage", "healthdrain"):
            self._damage(side, pet, victim_side, victim, action, source_damage)
        elif action.type == "healthheal":
            amount = self._roll(action, pet.healing)
            self._change_health(victim_side, victim, amount, element=action.link_type or pet.element)
            self._fx(victim_side, victim, action)
        elif action.type == "manachange":
            self._change_mana(victim_side, victim, self._roll(action, 100) // 100 or action.min_amount)
            self._fx(victim_side, victim, action)
        elif action.type == "none":
            self._fx(victim_side, victim, action)
        for buff in action.buffs:
            duration = max(1, action.min_amount)
            active = victim.add_buff(buff, duration, source_damage)
            self._message(BUFF_ADD, BATTLE_PLAYER_INDEX=victim_side.index, BATTLE_PET_INDEX=victim.index,
                          BATTLE_PET_BUFF_INDEX=active.index, BATTLE_PET_BUFF_ID=buff.id,
                          BATTLE_PET_BUFF_DURATION=duration)

    def _damage(self, side, pet, victim_side, victim, action, source_damage):
        element = action.link_type or pet.element
        if random.random() < MISS_CHANCE:
            self._message(MISS, BATTLE_SOURCE_PLAYER_INDEX=side.index, BATTLE_SOURCE_PET_INDEX=pet.index,
                          BATTLE_TARGET_PLAYER_INDEX=victim_side.index, BATTLE_TARGET_PET_INDEX=victim.index)
            return
        amount = self._roll(action, source_damage)
        amount *= 1 + pet.effect_amount("damageperc") / 100
        amount *= 1 - victim.effect_amount("resistperc") / 100
        modifier, _heal = self.data.modifier(element, victim.element)
        amount *= 1 + modifier
        if victim.defending:
            amount *= DEFEND_REDUCTION
        crit_chance = min(MAX_CRIT_CHANCE, pet.luck * CRIT_PER_LUCK / 100 + pet.effect_amount("critchance") / 100)
        crit = random.random() < crit_chance
        if crit:
            amount *= CRIT_MULTIPLIER
        amount = max(1, int(amount))
        if side.index == 0:
            self.stats["damage"] += amount
            by_element = self.stats["damage_by_element"]
            by_element[element] = by_element.get(element, 0) + amount
            self.stats["crits"] += 1 if crit else 0
        self._fx(victim_side, victim, action)
        self._change_health(victim_side, victim, -amount, element=element, crit=crit,
                            modifier=int(modifier * 100))
        if action.type == "healthdrain":
            self._change_health(side, pet, max(1, int(amount * (action.multiplier or 0.5))), element=element)

    def _roll(self, action, stat):
        low, high = sorted((action.min_amount, action.max_amount or action.min_amount))
        return max(1, int(stat * random.randint(low, high) / 100))

    def _change_health(self, side, pet, amount, element="", crit=False, modifier=0):
        if amount > 0 and side.index == 0:
            self.stats["healing"] += min(amount, pet.max_health - pet.health)
        pet.health = max(0, min(pet.max_health, pet.health + amount))
        self._message(HEALTH_CHANGE, BATTLE_PLAYER_INDEX=side.index, BATTLE_PET_INDEX=pet.index,
                      BATTLE_PET_CURRENT_HEALTH=pet.health, BATTLE_HEALTH_CHANGE=int(amount),
                      BATTLE_EFFECT_MODIFIER=int(modifier), BATTLE_EFFECT_CRIT=bool(crit),
                      BATTLE_EFFECT_TYPE=self._type_id(element))

    def _change_mana(self, side, pet, amount):
        before = pet.mana
        pet.mana = max(0, min(pet.max_mana, pet.mana + amount))
        if pet.mana != before:
            self._message(MANA_CHANGE, BATTLE_PLAYER_INDEX=side.index, BATTLE_PET_INDEX=pet.index,
                          BATTLE_PET_CURRENT_MANA=pet.mana, BATTLE_MANA_CHANGE=pet.mana - before,
                          BATTLE_EFFECT_MODIFIER=0, BATTLE_EFFECT_TYPE=self._type_id(pet.element))

    def _fx(self, side, pet, action):
        fx_id = self.data.fx_ids.get(action.fx)
        if fx_id is not None:
            self._message(FX, BATTLE_PLAYER_INDEX=side.index, BATTLE_PET_INDEX=pet.index, BATTLE_FX=fx_id)

    def _type_id(self, element):
        try:
            return self.data.types.index(element)
        except ValueError:
            return 0

    def _check_dead(self):
        for side in self.players:
            if side.current and side.current.is_dead:
                nxt = next((pet for pet in side.pets if not pet.is_dead), None)
                if nxt:
                    self._select_pet(side, nxt.index, end_turn=False)
                else:
                    side.current = None
        for side in self.players:
            if not side.alive_pets:
                self._finish(self.opponent(side))
                return

    # ---------------------------------------------------------------- enemy brain
    def _ai_turn(self, side):
        pet = side.current
        if not pet or pet.is_dead:
            nxt = next((p for p in side.pets if not p.is_dead), None)
            if not nxt:
                return
            self._select_pet(side, nxt.index, end_turn=False)
            pet = side.current
        if pet.has_effect(*STUNNING):
            self._message(ABILITY, BATTLE_PLAYER_INDEX=side.index, BATTLE_PET_INDEX=pet.index,
                          BATTLE_SKILL_ID=0, BATTLE_ABILITY_INDEX=1, BATTLE_PET_COOLDOWNS=pet.cooldowns)
            self._end_turn()
            return
        usable = [(skill, ability) for skill, ability in pet.abilities(self.data)
                  if ability.mana_cost <= pet.mana and not pet.cooldowns[skill.id]]
        if not usable:
            self._defend(side)
            return
        healing = [pair for pair in usable if any(a.type == "healthheal" for a in pair[1].actions)]
        if healing and pet.health < pet.max_health * 0.4:
            skill, ability = healing[0]
        else:
            attacks = [pair for pair in usable if any(a.type in ("healthdamage", "healthdrain") for a in pair[1].actions)]
            skill, ability = max(attacks or usable, key=lambda pair: max(
                (a.max_amount for a in pair[1].actions if a.type in ("healthdamage", "healthdrain")), default=0))
        self._resolve_ability(side, pet, skill, ability, self.opponent(side).current)

    # ---------------------------------------------------------------- end
    def _finish(self, winner):
        self.finished = True
        self.won = winner.index == 0
        self._message(COMPLETE, BATTLE_PLAYER_INDEX=winner.index)
        if self.won:
            self.rewards = self._award()

    def _award(self):
        gold = self.battle_ref.gold
        exp = self.node.exp
        self.player_save["gold"] += gold
        self.player_save["exp"] += exp
        self._award_pet_exp()
        results = self._message(RESULTS, BATTLE_GOLD=int(gold), BATTLE_EXP=int(exp), BATTLE_POINTS=0)
        results.set_esobject_array(K.ITEM_LIST, self._roll_loot())
        joined = self._roll_dna()
        if joined:
            # BattlePlugin only needs enough of a PetData to draw the window: PetRef comes from
            # PET_ID, and the curio does not exist in the collection yet (it is only an offer)
            offer = (EsObject().set_integer(K.PET_UID, 0)
                     .set_integer(K.PET_ID, joined["species_id"])
                     .set_string(K.PET_NAME, "")
                     .set_integer(K.PET_LEVEL, 1).set_integer(K.PET_PRESTIGE, 0)
                     .set_integer(K.PET_RANK, 0).set_integer(K.PET_FUSION, 0)
                     .set_integer(K.PET_SKIN, 0))
            results.set_esobject(K.BATTLE_JOINING_PET, offer)
            results.set_integer(K.BATTLE_JOINING_PETPERC, joined["perc"])
        return {"gold": gold, "exp": exp, "joined": joined}

    def _award_pet_exp(self):
        """Experience for the curios that fought, with the level ups it earns them."""
        gained = self.battle_ref.pet_exp
        if gained <= 0:
            return
        for fighter in self.players[0].pets:
            saved = next((pet for pet in self.player_save["pets"] if pet["uid"] == fighter.uid), None)
            if saved is None:
                continue
            levels = grant_exp(saved, fighter.species, self.data, gained)
            self.stats["level_ups"] += levels
            if levels:
                log.info("curio %s subiu para o nivel %d", fighter.species.name, saved["level"])

    def _roll_loot(self):
        """Materials dropped by a won fight, straight into the bag.

        The client asks for nothing here: ZoneNodeBattleRef has no loot field, so BattlePlugin
        simply shows whatever ITEM_LIST carries.  Without this the only source of materials was
        the 2500-gold Mystery Box, which put a single recipe out of reach for good.
        """
        from . import rewards
        table = self.data.battle_loot(self._average_enemy_level())
        granted = []
        for material_id, percent in table:
            if random.randint(1, 100) <= percent:
                granted.append(rewards.give(self.player_save, self.data, material_id,
                                            rewards.ITEM_MATERIAL, 1))
        # Shards of the curio just defeated.  They are indexed by SPECIES id (ShardBook builds
        # itself from PetBook, it has no book of its own), and this is the only way to get them:
        # nothing sells or grants shards, so without this drop rarity promotion is unreachable.
        # ItemLootWindow already special-cases shards, so this is the original's own channel.
        if self.players[1].pets and random.randint(1, 100) <= SHARD_DROP_CHANCE:
            beaten = random.choice(self.players[1].pets).species
            granted.append(rewards.give(self.player_save, self.data, beaten.id,
                                        rewards.ITEM_SHARD, 1))
        if granted:
            log.info("espolio: %d item(ns)", len(granted))
        return granted

    def _average_enemy_level(self):
        levels = [pet.level for pet in self.players[1].pets]
        return sum(levels) // len(levels) if levels else 1

    def _roll_dna(self):
        """Wild curios leave DNA behind, and the DNA IS the replication chance.

        PetPurchaseWindow shows it as SuccessBook.lookupColoredName(BATTLE_JOINING_PETPERC) and
        offers two lab processes: the gold button rolls against this percentage (MerchantDALC
        ROLL_CURIO), the plasma button buys the curio outright (PURCHASE_ITEM).  So the server
        must NOT hand the curio over here - it only reports how much DNA the player now holds.
        """
        chance = self.battle_ref.dna
        if chance <= 0 or not self.players[1].pets:
            return None
        species = random.choice(self.players[1].pets).species
        from . import rewards
        dna = self.player_save.setdefault("dna", {})
        key = str(species.id)
        total = dna.get(key, 0) + random.randint(max(1, chance // 2), chance)
        # DNA is a percentage and caps at 100; everything past that used to simply evaporate
        # (six saves were sitting at a wasted 100%).  The surplus now condenses into shards.
        extra, dna[key] = divmod(total, 100) if total > 100 else (0, total)
        if extra:
            rewards.give(self.player_save, self.data, species.id, rewards.ITEM_SHARD, extra)
            log.info("excedente de DNA de %s virou %d fragmento(s)", species.name, extra)
        # the client sends no id with ROLL_CURIO, so remember what this battle offered
        self.player_save["pending_roll"] = species.id
        log.info("DNA de %s agora em %d%%", species.name, dna[key])
        return {"species_id": species.id, "perc": dna[key]}
