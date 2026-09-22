"""Server-side view of the game data: parses the same Book XMLs the client receives,
so rules on both sides always agree."""
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("data")

STATS = ("health", "mana", "damage", "healing", "luck")
DIFFICULTY_TYPES = {"story": 0, "hard": 1, "challenge": 2, "elite": 3}


def _int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value):
    return str(value).lower() == "true"


def _ints(value):
    return [int(x) for x in str(value or "").split(",") if x.strip().lstrip("-").isdigit()]


@dataclass
class Bonus:
    """Percent and flat stat bonuses (prestiges, ranks and fusions all use this shape)."""
    perc: dict = field(default_factory=dict)
    gain: dict = field(default_factory=dict)

    @classmethod
    def from_attrs(cls, attrs):
        return cls({s: _float(attrs.get(s + "Perc")) for s in STATS},
                   {s: _int(attrs.get(s + "Gain")) for s in STATS})


@dataclass
class PetSkill:
    id: int
    link: str
    name: str
    start_rank: int
    level_req: int
    skills_req: list
    rank_costs: list
    required: bool


@dataclass
class Prestige:
    id: int
    max_level: int
    bonus: Bonus


@dataclass
class Species:
    id: int
    name: str
    rarity: str
    type: str
    starter: bool
    visible: bool
    base: dict
    gain: dict
    skills: list
    prestiges: list
    cost_gold: int = 0
    cost_credits: int = 0
    size: int = 1


@dataclass
class SkillEffect:
    type: str
    amount: int
    link_type: str


@dataclass
class SkillTrigger:
    type: str
    remove_buff: bool
    actions: list


@dataclass
class SkillBuff:
    id: int            # same numbering the client gives buffs while parsing SkillBook
    name: str
    type: str          # positive / negative / passive
    effects: list
    triggers: list


@dataclass
class SkillAction:
    type: str          # healthdamage, healthheal, healthdrain, manachange, none, ...
    min_amount: int
    max_amount: int
    multiplier: float
    source: str
    target: str
    link_type: str     # element the damage counts as
    fx: str
    buffs: list


@dataclass
class Ability:
    rank: int
    mana_cost: int
    health_cost: int
    cooldown: int
    instant: bool
    select_target: str
    actions: list
    element: object


@dataclass
class Battle:
    name: str
    health: int
    pets: list          # [(species id, level)]
    gold: int
    pet_exp: int
    dna: int
    element: object


@dataclass
class Node:
    zone_id: int
    difficulty: int
    id: int
    name: str
    energy: int
    exp: int
    tokens: int
    complete_zone: bool
    required_nodes: list
    unlock_nodes: list
    battle_bg: str
    battles: list

    @property
    def total_health(self):
        return max(1, sum(b.health for b in self.battles))


def _rewards(el):
    """(item id, item type, quantity) for every <item> under this element's <rewards>."""
    return [(_int(item.get("id")), item.get("type", "").lower(), max(1, _int(item.get("qty"), 1)))
            for item in el.iterfind("rewards/item")]


@dataclass
class JobRef:
    id: int
    name: str
    objective: str     # defeat, fight, level, plinko, obtain, upgrade
    count: int
    target: str        # node, pet, none, self, pvp
    pet_type: str      # element the defeated curio must be, empty when any will do
    rewards: list


@dataclass
class AchievementRank:
    id: int
    needed: int
    rewards: list


@dataclass
class AchievementRef:
    id: int
    name: str
    track: str         # what the server counts for it (node_wins, damage:<element>, ...)
    ranks: list


@dataclass
class WheelSlot:
    id: int
    item_type: str
    item_id: int
    qty: int
    weight: int


@dataclass
class Service:
    id: int
    type: str          # plinko, teamslot, energy, tickets, gold, skillreset, tokens, petmaxbonus, name_change
    name: str
    value: int
    cost_gold: int
    cost_credits: int


@dataclass
class GrabBagItem:
    id: int
    type: str
    qty: int
    perc: float


@dataclass
class GrabBag:
    id: int
    name: str
    roll: int
    cost_gold: int
    cost_credits: int
    items: list


@dataclass
class Consumable:
    """An "Enhancement": using one permanently raises one curio's stats.

    stats maps a stat to (normal, bonus); a curio whose element is in bonus_types gets the
    second number.  The client keeps the totals in PET_BONUS_* and reads them back at login.
    """
    id: int
    rarity: str
    name: str
    bonus_types: list
    stats: dict
    use_gold: int
    cost_gold: int
    cost_credits: int
    sell_gold: int


@dataclass
class Enchant:
    """A "Boost" slotted into one of a curio's three coloured sockets.

    slots holds the socket ids it fits (EnchantRef: red 1, yellow 2, blue 3).  upgrade_from is
    the client's `upgradeID`, which points at the PREVIOUS tier, not the next one.
    """
    id: int
    rarity: str
    name: str
    slots: list
    stats: dict
    destroy_gold: int
    upgrade_gold: int
    upgrade_from: int
    cost_gold: int = 0
    cost_credits: int = 0


@dataclass
class Craft:
    id: int
    tab: int
    items: list        # (item id, type name, quantity) the recipe consumes
    result: tuple      # (item id, type name, quantity) it produces


@dataclass
class WelcomePack:
    id: int
    name: str
    items: list        # (item id, type name, quantity), ready for rewards.give_all


@dataclass
class Skin:
    """An alternate look for one species.

    PetSkinWindow.getSkinIDs mixes two id spaces: negative ids (0, -1, -2) are the curio's own
    prestige looks, positive ids are SkinBook entries whose petID matches the species.
    """
    id: int
    pet_id: int
    name: str
    rarity: str


@dataclass
class Material:
    id: int
    rarity: str
    name: str
    cost_gold: int
    cost_credits: int
    sell_gold: int


class GameData:
    def __init__(self, books_dir):
        self.books_dir = Path(books_dir)
        self.reload()

    def reload(self):
        self.variables = self._load_variables()
        self.rarities = self._load_links("RarityBook.xml", "raritys/rarity")
        self.types = self._load_links("PetTypeBook.xml", "types/type")
        self.ranks = self._load_bonus_book("PetRankBook.xml", "ranks/rank")
        self.fusions = self._load_bonus_book("PetFusionBook.xml", "fusions/fusion")
        self.fusion_steps = self._load_fusion_steps()
        self.skills = self._load_skills()
        self.species = self._load_species()
        self.nodes = self._load_zones()
        self.services = self._load_services()
        self.grab_bags = self._load_grab_bags()
        self.consumables = self._load_consumables()
        self.materials = self._load_materials()
        self.skins = self._load_skins()
        self.welcome_packs = self._load_welcome_packs()
        self.crafts = self._load_crafts()
        self.loot_ladder = self._load_loot()
        self.enchants = self._load_enchants()
        self.shop_offers = self._load_shop_offers()
        self.jobs = self._load_jobs()
        self.achievements = self._load_achievements()
        self.rank_upgrades = self._load_rank_upgrades()
        self.rarity_costs = self._load_rarity_costs()
        self.rarity_cores = self._load_rarity_cores()
        self.rarity_promotion = self._load_rarity_promotion()
        self.rarity_exchange = self._load_rarity_exchange()
        self.wheel = self._load_wheel()
        self.plinko = self._load_plinko()
        self.daily = self._load_daily()
        self.zone_ids = sorted({(zone, difficulty) for zone, difficulty, _node in self.nodes})
        log.info("dados do jogo: %d curios, %d skills, %d nos de zona", len(self.species), len(self.skills), len(self.nodes))

    def _root(self, name):
        path = self.books_dir / name
        if not path.exists():
            log.warning("%s nao encontrado", name)
            return None
        return ET.parse(path).getroot()

    def var(self, name, default=0):
        return _int(self.variables.get(name), default)

    def _load_variables(self):
        root = self._root("VariableBook.xml")
        container = root.find("variables") if root is not None else None
        return {} if container is None else {child.tag: (child.text or "").strip() for child in container}

    def _load_links(self, book, path):
        root = self._root(book)
        return [] if root is None else [el.get("link", "").lower() for el in root.iterfind(path)]

    def _load_bonus_book(self, book, path):
        root = self._root(book)
        return {} if root is None else {_int(el.get("id")): Bonus.from_attrs(el.attrib) for el in root.iterfind(path)}

    def _load_skills(self):
        """Skills with their actions and buffs, exactly as the client reads SkillBook."""
        root = self._root("SkillBook.xml")
        self.fx_ids, self.modifiers = {}, {}
        skills = {}
        if root is None:
            return skills
        for index, fx in enumerate(root.iterfind("fx/fx")):
            self.fx_ids[fx.get("link", "").lower()] = index
        for modifier in root.iterfind("modifiers/modifier"):
            key = ((modifier.get("attackerType") or "").lower(), (modifier.get("defenderType") or "").lower())
            self.modifiers[key] = (_float(modifier.get("damageMultiplier")), _float(modifier.get("healMultiplier")))
        container = root.find("skills")
        if container is None:
            return skills
        # the client numbers buffs in document order while parsing, and battle messages use
        # those numbers, so the server has to arrive at the same ids
        buff_ids = {id(buff): number for number, buff in enumerate(container.iter("buff"))}
        for el in container.iterfind("skill"):
            skills[el.get("link", "").lower()] = [
                Ability(rank, _int(ab.get("manaCost")), _int(ab.get("healthCost")), _int(ab.get("cooldown")),
                        _bool(ab.get("instant")), (ab.get("selectTarget") or "").lower(),
                        self._actions(ab, buff_ids), ab)
                for rank, ab in enumerate(el.iterfind("ability"), start=1)
            ]
        return skills

    def _actions(self, parent, buff_ids):
        return [SkillAction((el.get("type") or "none").lower(), _int(el.get("minAmount")), _int(el.get("maxAmount")),
                            _float(el.get("multiplier")), (el.get("source") or "").lower(),
                            (el.get("target") or "").lower(), (el.get("linkType") or "").lower(),
                            (el.get("fx") or "").lower(), self._buffs(el, buff_ids))
                for el in parent.iterfind("action")]

    def _buffs(self, parent, buff_ids):
        buffs = []
        for el in parent.iterfind("buff"):
            effects = [SkillEffect((e.get("type") or "none").lower(), _int(e.get("amount")),
                                   (e.get("linkType") or "").lower()) for e in el.iterfind("effect")]
            triggers = [SkillTrigger((t.get("type") or "none").lower(), _bool(t.get("removeBuff")),
                                     self._actions(t, buff_ids)) for t in el.iterfind("trigger")]
            buffs.append(SkillBuff(buff_ids[id(el)], el.get("name", ""), (el.get("type") or "none").lower(),
                                   effects, triggers))
        return buffs

    def modifier(self, attacker_type, defender_type):
        """Damage/heal multipliers of the element wheel (Strong/Weak in the client's battle log)."""
        return self.modifiers.get((attacker_type, defender_type), (0.0, 0.0))

    def _load_species(self):
        root = self._root("PetBook.xml")
        species = {}
        if root is None:
            return species
        for el in root.iterfind("pets/pet"):
            stats = el.find("stats")
            attrs = stats.attrib if stats is not None else {}
            skills = [PetSkill(_int(s.get("id")), s.get("link", "").lower(), s.get("name", ""), _int(s.get("startRank")),
                               _int(s.get("levelReq")), _ints(s.get("skillsReq")), _ints(s.get("rankCosts")),
                               _bool(s.get("required")))
                      for s in el.iterfind("skills/skill")]
            prestiges = [Prestige(_int(p.get("id")), _int(p.get("maxLevel")), Bonus.from_attrs(p.attrib))
                         for p in el.iterfind("prestiges/prestige")]
            pet_id = _int(el.get("id"))
            species[pet_id] = Species(pet_id, el.get("name", ""), el.get("rarity", "").lower(), el.get("type", "").lower(),
                                      _bool(el.get("starter")), _bool(el.get("visible")),
                                      {s: _int(attrs.get(s + "Base")) for s in STATS},
                                      {s: _int(attrs.get(s + "Gain")) for s in STATS},
                                      skills, prestiges, _int(el.get("costGold")), _int(el.get("costCredits")),
                                      _int(el.get("size"), 1))
        return species

    def _load_services(self):
        root = self._root("ServiceBook.xml")
        services = {}
        for el in [] if root is None else root.iterfind(".//service"):
            service_id = _int(el.get("id"))
            services[service_id] = Service(service_id, el.get("type", "").lower(), el.get("name", ""),
                                           _int(el.get("value")), _int(el.get("costGold")), _int(el.get("costCredits")))
        return services

    def _load_grab_bags(self):
        root = self._root("GrabBagBook.xml")
        bags = {}
        for el in [] if root is None else root.iterfind(".//grabbag"):
            bag_id = _int(el.get("id"))
            items = [GrabBagItem(_int(item.get("id")), item.get("type", "").lower(), _int(item.get("qty"), 1),
                                 _float(item.get("perc")))
                     for item in el.iterfind("items/item")]
            bags[bag_id] = GrabBag(bag_id, el.get("name", ""), max(1, _int(el.get("roll"), 1)),
                                   _int(el.get("costGold")), _int(el.get("costCredits")), items)
        return bags

    def _load_consumables(self):
        root = self._root("ConsumableBook.xml")
        consumables = {}
        for el in [] if root is None else root.iterfind(".//consumable"):
            cid = _int(el.get("id"))
            stats = {stat: (_int(el.get(stat)), _int(el.get("bonus" + stat.capitalize())))
                     for stat in ("health", "damage", "healing", "mana", "luck")}
            consumables[cid] = Consumable(
                cid, el.get("rarity", ""), el.get("name", ""),
                [t for t in (el.get("bonusTypes") or "").split(",") if t],
                {stat: pair for stat, pair in stats.items() if pair != (0, 0)},
                _int(el.get("useGold")), _int(el.get("costGold")), _int(el.get("costCredits")),
                _int(el.get("sellGold")))
        return consumables

    SLOT_IDS = {"red": 1, "yellow": 2, "blue": 3}

    def _load_enchants(self):
        root = self._root("EnchantBook.xml")
        enchants = {}
        for el in [] if root is None else root.iterfind(".//enchant"):
            enchant_id = _int(el.get("id"))
            slots = [self.SLOT_IDS[name] for name in (el.get("slots") or "").split(",")
                     if name.strip() in self.SLOT_IDS]
            stats = {stat: _int(el.get(stat)) for stat in ("health", "mana", "damage", "healing", "luck")}
            enchants[enchant_id] = Enchant(
                enchant_id, el.get("rarity", ""), el.get("name", ""), slots,
                {stat: value for stat, value in stats.items() if value},
                _int(el.get("destroyGold")), _int(el.get("upgradeGold")), _int(el.get("upgradeID")),
                _int(el.get("costGold")), _int(el.get("costCredits")))
        return enchants

    def upgrade_of(self, enchant_id):
        """The enchant that upgrades this one, mirroring EnchantBook.getUpgradeEnchant.

        Guarded against 0: a tier-1 enchant has no upgradeID, which loads as 0, so asking
        "what upgrades 0" would otherwise hand back the first tier-1 enchant by accident.
        """
        if not enchant_id:
            return None
        return next((e for e in self.enchants.values() if e.upgrade_from == enchant_id), None)

    def battle_loot(self, level):
        """(material id, percent) for a fight of this average level.

        The table is a ladder: the entry with the highest threshold at or below the level wins.
        It is server-side only - ZoneNodeBattleRef has no loot field for the client to read.
        """
        chosen = []
        for threshold, table in self.loot_ladder:
            if level >= threshold:
                chosen = table
        return chosen

    def _load_loot(self):
        root = self._root("VariableBook.xml")
        ladder = []
        for el in [] if root is None else root.iterfind("battleLoot/tier"):
            drops = [(_int(d.get("id")), _int(d.get("perc")))
                     for d in el.iterfind("drop")]
            ladder.append((_int(el.get("level")), drops))
        return sorted(ladder)

    def _load_crafts(self):
        root = self._root("CraftBook.xml")
        crafts = {}
        for el in [] if root is None else root.iterfind("craft"):
            craft_id = _int(el.get("id"))
            result = el.find("result")
            if result is None:
                continue
            crafts[craft_id] = Craft(
                craft_id, _int(el.get("tab")),
                [(_int(i.get("id")), i.get("type", "").lower(), _int(i.get("qty"), 1))
                 for i in el.iterfind("items/item")],
                (_int(result.get("id")), result.get("type", "").lower(), _int(result.get("qty"), 1)))
        return crafts

    def _load_welcome_packs(self):
        root = self._root("WelcomePackBook.xml")
        packs = {}
        for el in [] if root is None else root.iterfind("welcomePack"):
            pack_id = _int(el.get("id"))
            items = [(_int(item.get("id")), item.get("type", "").lower(), _int(item.get("qty"), 1))
                     for item in el.iterfind("items/item")]
            packs[pack_id] = WelcomePack(pack_id, el.get("name", ""), items)
        return packs

    def _load_skins(self):
        root = self._root("SkinBook.xml")
        skins = {}
        for el in [] if root is None else root.iterfind(".//skin"):
            skin_id = _int(el.get("id"))
            skins[skin_id] = Skin(skin_id, _int(el.get("petID")), el.get("name", ""), el.get("rarity", ""))
        return skins

    def _load_materials(self):
        root = self._root("MaterialBook.xml")
        materials = {}
        for el in [] if root is None else root.iterfind(".//material"):
            mid = _int(el.get("id"))
            materials[mid] = Material(mid, el.get("rarity", ""), el.get("name", ""),
                                      _int(el.get("costGold")), _int(el.get("costCredits")),
                                      _int(el.get("sellGold")))
        return materials

    def _load_rank_upgrades(self):
        """rank id -> (item id, item type, quantity, next rank).  PetUpgradeRankPanel prices the
        next rank with the item sitting on the rank the curio already holds."""
        root = self._root("PetRankBook.xml")
        upgrades = {}
        for el in [] if root is None else root.iterfind(".//rank"):
            upgrades[_int(el.get("id"))] = (_int(el.get("itemID"), -1), el.get("itemType", "").lower(),
                                            _int(el.get("itemQty")), _int(el.get("upgradeRank"), -1))
        return upgrades

    def _load_fusion_steps(self):
        """fusion id -> (duplicates it costs, fusion id it becomes).

        _load_bonus_book only keeps the stat bonuses, so the upgrade cost never reached the
        server: without this the fusion action has no idea how many duplicates to consume.
        A step of -1 means the chain ends there.
        """
        root = self._root("PetFusionBook.xml")
        steps = {}
        for el in [] if root is None else root.iterfind("fusions/fusion"):
            steps[_int(el.get("id"))] = (_int(el.get("upgradeDupes"), -1),
                                         _int(el.get("upgradeFusion"), -1))
        return steps

    def next_rarity(self, rarity):
        """The rarity above this one, or None at the top (RarityBook order is the ladder)."""
        try:
            return self.rarities[self.rarities.index(str(rarity).lower()) + 1]
        except (ValueError, IndexError):
            return None

    def _load_rarity_promotion(self):
        """rarity index -> (promotion shards, promotion gold, summon shards, summon gold).

        Indexed by POSITION, because RarityPetOverrides walks the override's children in order
        and treats the position as the rarity; the child tag name is never read.
        """
        root = self._root("RarityOverrideBook.xml")
        override = root.find("overrides/rarityOverride") if root is not None else None
        table = {}
        for index, el in enumerate([] if override is None else list(override)):
            table[index] = (_int(el.get("promotionShards")), _int(el.get("promotionGoldCost")),
                            _int(el.get("summonShards")), _int(el.get("summonGoldCost")))
        return table

    def _load_rarity_cores(self):
        """rarity -> (epic, legendary, mythic) core pieces an exchanged curio of it is worth.

        PetExchangeWindow adds these up off the RarityBook, and they are the only feed for
        rarity promotion, so the server has to agree with what the client displays.
        """
        root = self._root("RarityBook.xml")
        cores = {}
        for el in [] if root is None else root.iterfind(".//rarity"):
            cores[el.get("link", "").lower()] = (_int(el.get("exchangeEpicCorePieces")),
                                                 _int(el.get("exchangeLegendaryCorePieces")),
                                                 _int(el.get("exchangeMythicCorePieces")))
        return cores

    def _load_rarity_costs(self):
        """rarity -> {prestige id: gold}, the price RarityBook puts on each evolution."""
        root = self._root("RarityBook.xml")
        costs = {}
        for el in [] if root is None else root.iterfind(".//rarity"):
            costs[el.get("link", "").lower()] = {_int(p.get("id")): _int(p.get("costGold"))
                                                 for p in el.findall("prestige")}
        return costs

    def _load_daily(self):
        """day of the login streak -> (item id, item type, quantity) it hands out."""
        root = self._root("DailyBook.xml")
        days = {}
        for el in [] if root is None else root.iterfind(".//daily"):
            days[_int(el.get("day"))] = [(_int(item.get("id")), item.get("type", "").lower(),
                                          max(1, _int(item.get("qty"), 1)))
                                         for item in el.iterfind("items/item")]
        return days

    def _load_plinko(self):
        """slot id -> the weighted prize table behind it.  PlinkoBook only tells the client where
        the slots are; what each one pays is decided here, like the prize wheel."""
        root = self._root("PlinkoBook.xml")
        slots = {}
        for el in [] if root is None else root.iterfind(".//plinko"):
            slots[_int(el.get("position", el.get("id")))] = [
                GrabBagItem(_int(item.get("id")), item.get("type", "").lower(),
                            max(1, _int(item.get("qty"), 1)), _float(item.get("perc")))
                for item in el.iterfind("items/item")]
        return slots

    def _load_wheel(self):
        """The prize wheel is decided here: PrizeWheelBook only tells the client which icons to draw,
        so the prize behind each slot lives on the server (PrizeWheelScreen just lights the slot)."""
        root = self._root("PrizeWheelBook.xml")
        slots = []
        for el in [] if root is None else root.iterfind(".//spinReward"):
            slots.append(WheelSlot(_int(el.get("id")), el.get("itemType", "").lower(), _int(el.get("itemID")),
                                   max(1, _int(el.get("qty"), 1)), max(0, _int(el.get("weight")))))
        return sorted(slots, key=lambda slot: slot.id)

    def _load_rarity_exchange(self):
        """rarity -> (base experience, multiplier) paid for trading a curio away."""
        root = self._root("RarityBook.xml")
        values = {}
        for el in [] if root is None else root.iterfind(".//rarity"):
            values[el.get("link", "").lower()] = (_int(el.get("exchangeExpBase")),
                                                  _float(el.get("exchangeExpMult"), 1.0))
        return values

    def _load_jobs(self):
        root = self._root("JobBook.xml")
        jobs = {}
        for el in [] if root is None else root.iterfind(".//job"):
            job_id = _int(el.get("id"))
            jobs[job_id] = JobRef(job_id, el.get("name", ""), el.get("objective", "").lower(),
                                  max(1, _int(el.get("count"), 1)), el.get("target", "").lower(),
                                  el.get("petType", "").lower(), _rewards(el))
        return jobs

    def _load_achievements(self):
        root = self._root("AchievementBook.xml")
        achievements = {}
        for el in [] if root is None else root.iterfind(".//achievement"):
            achievement_id = _int(el.get("id"))
            ranks = [AchievementRank(_int(rank.get("id")), max(1, _int(rank.get("amtNeeded"), 1)), _rewards(rank))
                     for rank in el.iterfind("ranks/rank")]
            achievements[achievement_id] = AchievementRef(achievement_id, el.get("name", ""),
                                                          el.get("track", "").lower(), ranks)
        return achievements

    def _load_shop_offers(self):
        """(type, id) of everything a shop tab lists, so nothing else can be bought."""
        root = self._root("ShopBook.xml")
        return set() if root is None else {(el.get("type", "").lower(), _int(el.get("id")))
                                           for el in root.iterfind(".//items/item")}

    def _load_zones(self):
        root = self._root("ZoneBook.xml")
        nodes = {}
        if root is None:
            return nodes
        for zone_el in root.iterfind("zones/zone"):
            zone_id = _int(zone_el.get("id"))
            zone_root = self._root(zone_el.get("xml", ""))
            if zone_root is None:
                continue
            for zone in zone_root.iterfind("zone"):
                for difficulty in zone.iterfind("difficulty"):
                    dtype = DIFFICULTY_TYPES.get((difficulty.get("type") or "").lower(), 0)
                    for n in difficulty.iterfind("nodes/node"):
                        battles = [Battle(b.get("name", ""), _int(b.get("health")),
                                          [(_int(p.get("id")), _int(p.get("level"), 1)) for p in b.iterfind("pets/pet")],
                                          _int(b.get("gold")), _int(b.get("petExp")), _int(b.get("dna")), b)
                                   for b in n.iterfind("battles/battle")]
                        node = Node(zone_id, dtype, _int(n.get("id")), n.get("name", ""), _int(n.get("energy")),
                                    _int(n.get("exp")), _int(n.get("tokens")), _bool(n.get("completeZone")),
                                    _ints(n.get("requiredNodes")), _ints(n.get("unlockNodes")), n.get("battleBG", ""),
                                    battles)
                        nodes[(zone_id, dtype, node.id)] = node
        return nodes

    def starter_ids(self):
        return [s.id for s in self.species.values() if s.starter]

    def stat(self, species, stat, level, prestige=0, rank=0, fusion=0):
        """Same formula as the client (model.pet.PetData.getStat), without collection/enchant bonuses."""
        sources = [species.prestiges[prestige].bonus if 0 <= prestige < len(species.prestiges) else None,
                   self.ranks.get(rank), self.fusions.get(fusion)]
        perc = 1 + sum(src.perc.get(stat, 0) for src in sources if src)
        extra = sum(src.gain.get(stat, 0) for src in sources if src)
        return int((species.base[stat] + species.gain[stat] * (level - 1) + extra) * perc)

    def max_level(self, species, prestige):
        if 0 <= prestige < len(species.prestiges):
            return species.prestiges[prestige].max_level
        return 1
