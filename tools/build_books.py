"""Builds the game data ("Books") that the client downloads at login.

Reads tools/content.py and data/design/species.json and writes:
  server/content/books/*.xml         the 44 Books plus the zone files
  server/content/asset_aliases.json  CDN-only art paths -> art bundled in the APK

Every asset the Books reference is checked against the original APK, and the text
markup is validated, because the client crashes on bad references.

    python tools/build_books.py [--apk "Curio Quest_1.15.00.apk"]
"""
import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import content as C

ROOT = Path(__file__).resolve().parent.parent
BOOKS_DIR = ROOT / "server" / "content" / "books"
ALIASES_PATH = ROOT / "server" / "content" / "asset_aliases.json"
SPECIES_PATH = ROOT / "data" / "design" / "species.json"
DEFAULT_APK = ROOT / "Curio Quest_1.15.00.apk"

ICON_PREFIX = {"physical": "Physical", "air": "Air", "earth": "Earth", "light": "Light", "dark": "Dark",
               "electric": "Electric", "water": "Water", "fire": "Fire"}
TYPE_ICON = {"physical": "Physical_Punch.png", "air": "Air_Attack_1.png", "earth": "Earth_Attack_1.png",
             "light": "Light_Attack_1.png", "dark": "Dark_Attack_1.png", "electric": "Electric_Attack_1.png",
             "water": "Water_Attack_1.png", "fire": "Fire_Attack_1.png"}

FX_SERIES = {
    "physical": ("rock_1", "rock_2", "rock_3", "rock_4"),
    "air": ("wind_1", "wind_2", "wind_3", "wind_4"),
    "earth": ("plant_1", "rock_2", "plant_3", "rock_4"),
    "light": ("light_1", "light_2", "light_3", "light_4"),
    "dark": ("dark_1", "dark_2", "dark_3", "darkblast"),
    "electric": ("electric_1", "electric_2", "electric_3", "electric_4"),
    "water": ("water_1", "water_2", "water_3", "water_4"),
    "fire": ("fire_1", "fire_2", "fire_3", "flamestrike"),
}
BASIC_FX = {"basic_claw": "scratch", "basic_blade": "slash", "basic_impact": "rock_1"}

# (mana cost, cooldown) and per-rank values for each skill slot
SLOT_COSTS = {"basic": (0, 0), "strike": (1, 1), "blast": (2, 2), "storm": (3, 3), "fury": (4, 3),
              "mend": (2, 2), "rally": (3, 3), "guard": (1, 3), "focus": (1, 3), "burn": (2, 3),
              "curse": (2, 3), "drain": (2, 2), "shock": (3, 4), "meditate": (0, 3)}
SLOT_RANKS = {
    "basic": ((80, 100), (85, 105), (90, 110), (95, 115), (100, 125)),
    "strike": ((110, 130), (120, 140), (130, 150), (140, 165)),
    "blast": ((160, 190), (175, 205), (190, 220), (205, 240)),
    "storm": ((55, 70), (65, 80), (75, 90)),
    "fury": ((240, 300), (270, 330), (300, 360)),
    "mend": ((150, 180), (170, 200), (190, 220), (210, 245)),
    "rally": ((60, 80), (70, 90), (80, 100)),
    "guard": (30, 40, 50),
    "focus": (20, 30, 40),
    "burn": (((60, 80), (25, 30)), ((70, 90), (30, 35)), ((80, 100), (35, 40))),
    "curse": (((60, 80), (25, 30)), ((70, 90), (30, 35)), ((80, 100), (35, 40))),
    "drain": ((90, 110), (100, 120), (110, 130), (120, 145)),
    "shock": ((80, 100), (90, 110), (100, 120)),
    "meditate": (2, 3, 4),
}
# skill points needed to reach each rank (index = current rank)
SLOT_RANK_COSTS = {"basic": (0, 1, 1, 2, 2), "strike": (0, 1, 2, 2), "blast": (2, 1, 2, 2), "storm": (3, 2, 3),
                   "fury": (4, 2, 3), "mend": (2, 1, 2, 2), "rally": (3, 2, 3), "guard": (2, 2, 2),
                   "focus": (2, 2, 2), "burn": (2, 2, 3), "curse": (2, 2, 3), "drain": (2, 1, 2, 2),
                   "shock": (3, 2, 3), "meditate": (1, 1, 1)}
GUARD_TURNS, FOCUS_TURNS, DOT_TURNS, STUN_TURNS = 2, 3, 3, 1


def fmt(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def el(parent, tag, text=None, **attrs):
    attrs = {key: fmt(value) for key, value in attrs.items() if value is not None}
    node = ET.Element(tag, attrs) if parent is None else ET.SubElement(parent, tag, attrs)
    if text is not None:
        node.text = text
    return node


class Apk:
    """Asset files bundled in the APK (paths as the client builds them, e.g. assets/images/...)."""

    def __init__(self, path):
        self.names = {}
        if path and Path(path).is_file():
            with zipfile.ZipFile(path) as apk:
                for name in apk.namelist():
                    if name.startswith("assets/assets/"):
                        self.names[name[len("assets/"):].lower()] = name[len("assets/"):]
        else:
            print(f"AVISO: APK nao encontrado ({path}); os assets nao serao conferidos", file=sys.stderr)

    @property
    def available(self):
        return bool(self.names)

    def find(self, rel):
        return self.names.get(rel.lower())


# Project.as:420-465 chama os Book.init() nesta ordem fixa.  So os nomes que importam para a
# resolucao de itens estao aqui, na posicao real.
BOOK_INIT_ORDER = [
    "RarityOverrideBook.xml", "PetTypeBook.xml", "SkillBook.xml", "PetBook.xml", "ShardBook.xml",
    "MaterialBook.xml", "CurrencyBook.xml", "ServiceBook.xml", "ConsumableBook.xml",
    "SkinBook.xml", "EnchantBook.xml", "WelcomePackBook.xml", "TimedModifierBook.xml",
    "GrabBagBook.xml", "VariableBook.xml", "PetRankBook.xml", "CraftBook.xml",
    "PvPEventBook.xml", "PvEEventBook.xml", "GvGEventBook.xml", "GvEEventBook.xml",
    "FvFEventBook.xml", "JobBook.xml", "AchievementBook.xml", "ShopBook.xml", "DailyBook.xml",
    "ReferBook.xml", "NewsBook.xml", "LimitedOfferBook.xml",
]

# ItemBook.lookup despacha o tipo para estes livros.
ITEM_TYPE_BOOK = {
    "pet": "PetBook.xml", "shard": "ShardBook.xml", "material": "MaterialBook.xml",
    "currency": "CurrencyBook.xml", "service": "ServiceBook.xml",
    "consumable": "ConsumableBook.xml", "skin": "SkinBook.xml", "enchant": "EnchantBook.xml",
    "welcomepack": "WelcomePackBook.xml", "timedModifier": "TimedModifierBook.xml",
    "grabbag": "GrabBagBook.xml",
}

# Livros cujo parseXML chama ItemData.fromXml/ItemBook.lookup (levantado do AS3 decompilado).
BOOKS_RESOLVING_ITEMS = [
    "WelcomePackBook.xml", "VariableBook.xml", "PetRankBook.xml", "CraftBook.xml",
    "PvPEventBook.xml", "PvEEventBook.xml", "GvGEventBook.xml", "GvEEventBook.xml",
    "FvFEventBook.xml", "JobBook.xml", "AchievementBook.xml", "ShopBook.xml", "DailyBook.xml",
    "ReferBook.xml", "NewsBook.xml", "LimitedOfferBook.xml",
]


class Builder:
    def __init__(self, apk, local=True):
        self.apk = apk
        self.local = local
        self.books = {}
        self.aliases = {}
        self.errors = []
        self.warnings = []
        self.species = self._load_species()
        self.by_asset = {s["asset"]: s for s in self.species}

    # ---------------------------------------------------------------- helpers
    def need(self, rel, what):
        if self.apk.available and not self.apk.find(rel):
            self.errors.append(f"{what}: asset ausente no APK: {rel}")

    def alias(self, wanted, source):
        if self.apk.available and not self.apk.find(source):
            self.errors.append(f"alias para asset inexistente: {wanted} -> {source}")
        self.aliases[wanted] = self.apk.find(source) or source

    def book(self, name):
        root = ET.Element("data")
        self.books[name] = root
        return root

    def item(self, parent, kind, ref, qty=1, **extra):
        item_id = C.CURRENCY_ID[ref] if kind == "currency" else ref
        return el(parent, "item", id=item_id, type=kind, qty=qty, **extra)

    @staticmethod
    def _load_species():
        data = json.loads(SPECIES_PATH.read_text(encoding="utf-8"))
        return [dict(s, id=index) for index, s in enumerate(data["species"], start=1)]

    # ---------------------------------------------------------------- books
    def build(self):
        self.tip_book()
        self.sound_book()
        self.rarity_books()
        self.type_book()
        self.skill_book_and_pets()
        self.currency_book()
        self.service_book()
        self.grab_bag_book()
        self.variable_book()
        self.rank_and_fusion_books()
        self.dialog_book()
        self.zone_books()
        self.plinko_book()
        self.achievement_book()
        self.job_book()
        self.shop_book()
        self.daily_book()
        self.prize_wheel_book()
        self.success_book()
        self.consumable_book()
        self.material_book()
        self.skin_book()
        self.welcome_pack_book()
        self.craft_book()
        self.enchant_book()
        self.video_offer_book()
        self.guild_book()
        self.empty_books()
        self.validate_text()

    def tip_book(self):
        root = self.book("TipBook.xml")
        for tip in C.TIPS:
            el(root, "tip", text=tip)

    def sound_book(self):
        root = self.book("SoundBook.xml")
        sounds = [("click", "Click.mp3", 1), ("evolve", "Evolve.mp3", 1), ("level_up", "Level_Up.mp3", 1),
                  ("wheel_spin", "Wheel_Spin.mp3", 1), ("purchase", "Purchase.mp3", 1),
                  ("arcade_button", "Arcade_Button.mp3", 1), ("arcade_peg", "Arcade_Peg.mp3", 0.6),
                  ("arcade_reward", "Arcade_Reward.mp3", 1), ("defend", "Defend.mp3", 0.8), ("heal", "Heal.mp3", 0.8)]
        for link, prefix in (("dark", "Dark"), ("electric", "Electric"), ("fire", "Fire"), ("ice", "Ice"),
                             ("light", "Light"), ("plants", "Plants"), ("rock", "Rock"), ("water", "Water"),
                             ("wind", "Wind")):
            sounds += [(f"{link}_{tier}", f"{prefix}_Attack_Tier_{tier}.mp3", 0.8) for tier in range(1, 5)]
        self.sound_links = set()
        for link, url, volume in sounds:
            self.need("assets/audio/sound/" + url, "SoundBook")
            el(root, "sound", link=link, url=url, volume=float(volume), loadLocal=True)
            self.sound_links.add(link)

    def rarity_books(self):
        root = el(self.book("RarityBook.xml"), "raritys")
        for index, link in enumerate(C.RARITIES):
            info = C.RARITY_INFO[link]
            scale = index + 1
            epic_pieces, legendary_pieces, mythic_pieces = C.RARITY_CORE_PIECES[link]
            rarity = el(root, "rarity", link=link, name=info["name"], color=info["color"],
                        exchangeExpBase=info["exchange_exp"], exchangeExpMult=1.0, exchangeConfirm=index >= 2,
                        exchangeEpicCorePieces=epic_pieces or None,
                        exchangeLegendaryCorePieces=legendary_pieces or None,
                        exchangeMythicCorePieces=mythic_pieces or None,
                        maxBonusDamage=50 * scale, maxBonusHealing=50 * scale, maxBonusHealth=400 * scale,
                        maxBonusMana=scale, maxBonusLuck=10 * scale)
            for prestige, gold in enumerate((0,) + tuple(info["prestige_gold"])):
                el(rarity, "prestige", id=prestige, costGold=gold)
        overrides = el(self.book("RarityOverrideBook.xml"), "overrides")
        # RarityPetOverrides reads param1.children() in order, so each child IS a rarity by
        # position; the tag name is never looked at, only the attributes.
        default = el(overrides, "rarityOverride", id="default", default=True)
        for link, promo_shards, promo_gold, summon_shards, summon_gold in C.RARITY_PROMOTION:
            el(default, "rarity", link=link,
               promotionShards=promo_shards or None, promotionGoldCost=promo_gold or None,
               summonShards=summon_shards or None, summonGoldCost=summon_gold or None)

    def type_book(self):
        root = el(self.book("PetTypeBook.xml"), "types")
        for link in C.ELEMENTS:
            icon = C.ELEMENT_NAMES[link] + ".png"
            el(root, "type", name=C.ELEMENT_NAMES[link], link=link, icon=icon, visible=True)
            self.alias("assets/images/pets/type/" + icon, "assets/images/abilities/icon/" + TYPE_ICON[link])
        # the landing screen asks for the arena background as a SWF, which the app never shipped;
        # Flash's Loader reads a JPEG just as happily, so point it at the picture that does exist
        self.alias("assets/swfs/battle/Colosseum.swf", "assets/images/battle/Colosseum.jpg")

    # ---------------------------------------------------------------- skills and curios
    def skill_book_and_pets(self):
        skill_root = self.book("SkillBook.xml")
        fx_root = el(skill_root, "fx")
        self.fx_links = set()
        fx = [("defend", "Defend.swf", "defend"), ("evolution", "Evolution.swf", "evolve"),
              ("scratch", "Scratch.swf", "rock_1"), ("slash", "Slash.swf", "rock_2"), ("gunshot", "GunShot.swf", "rock_3"),
              ("heal_1", "Generic_Heal_1.swf", "heal"), ("heal_2", "Generic_Heal_2.swf", "heal"),
              ("darkblast", "DarkBlast.swf", "dark_4"), ("flamestrike", "FlameStrike.swf", "fire_4"),
              ("electricattack", "ElectricAttack.swf", "electric_3")]
        for link, prefix, sound, count in (("fire", "Fire", "fire", 4), ("water", "Water", "water", 4),
                                           ("electric", "Electric", "electric", 4), ("light", "Light", "light", 4),
                                           ("dark", "Dark", "dark", 3), ("plant", "Plant", "plants", 4),
                                           ("rock", "Rock", "rock", 4), ("wind", "Wind", "wind", 4), ("ice", "Ice", "ice", 2)):
            fx += [(f"{link}_{n}", f"{prefix}_Attack_{n}.swf", f"{sound}_{n}") for n in range(1, count + 1)]
        for link, asset, sound in fx:
            self.need("assets/swfs/effects/" + asset, "SkillBook fx")
            if sound not in self.sound_links:
                self.errors.append(f"fx {link}: som inexistente {sound}")
            el(fx_root, "fx", link=link, asset=asset, scale=1.0, sound=sound, loadLocal=True)
            self.fx_links.add(link)

        modifiers = el(skill_root, "modifiers")
        for attacker, defenders in C.STRONG_AGAINST.items():
            for defender in defenders:
                el(modifiers, "modifier", attackerType=attacker, defenderType=defender,
                   damageMultiplier=C.STRONG_MULTIPLIER, healMultiplier=0.0)
                if attacker not in C.STRONG_AGAINST.get(defender, ()):
                    el(modifiers, "modifier", attackerType=defender, defenderType=attacker,
                       damageMultiplier=C.WEAK_MULTIPLIER, healMultiplier=0.0)

        skills_el = el(skill_root, "skills")
        built_skills = set()
        pets_root = el(self.book("PetBook.xml"), "pets")
        found_in = self._found_in()
        for s in self.species:
            kit = self._kit(s)
            for link, slot, element, _name, _icon in kit:
                if link not in built_skills:
                    self._skill(skills_el, link, slot, element)
                    built_skills.add(link)
            self._pet(pets_root, s, kit, found_in.get(s["asset"]))
        self.skill_links = built_skills

    def _kit(self, s):
        element, asset = s["element"], s["asset"]
        if asset in C.KIT_OVERRIDES:
            slots = list(C.KIT_OVERRIDES[asset])
        else:
            slots = [({"role": C.ROLE_SKILL[element], "extra": C.EXTRA_SKILL[element]}.get(slot, slot), None)
                     for slot in C.KITS[s["rarity"]]]
        kit = []
        for slot, name in slots:
            if slot == "basic":
                link, default_name, icon = C.BASIC_ATTACKS[asset]
                kit.append((link, "basic", "physical", name or default_name, icon))
                continue
            prefix = ICON_PREFIX[element]
            icon = {"strike": f"{prefix}_Attack_1.png", "blast": f"{prefix}_Attack_2.png",
                    "storm": f"{prefix}_Attack_3.png", "fury": f"{prefix}_Attack_4.png",
                    "drain": f"{prefix}_Attack_2.png", "burn": "Fire_Attack_3.png", "curse": "Dark_Attack_3.png",
                    "shock": "Electric_Attack_2.png"}.get(slot, f"{prefix}_Heal_1.png")
            if element == "earth" and slot in ("blast", "fury"):
                icon = "Rock_Attack_2.png" if slot == "blast" else "Rock_Attack_4.png"
            kit.append((f"{element}_{slot}", slot, element, name or C.SKILL_NAMES[element].get(slot, slot.title()), icon))
        return kit

    def _skill(self, parent, link, slot, element):
        skill = el(parent, "skill", link=link)
        mana, cooldown = SLOT_COSTS[slot]
        series = FX_SERIES[element]
        fx = {"basic": BASIC_FX.get(link), "strike": series[0], "blast": series[1], "storm": series[2],
              "fury": series[3], "drain": series[1], "burn": "fire_2", "curse": "dark_2", "shock": "electricattack",
              "mend": "heal_1", "rally": "heal_2", "guard": "heal_1", "focus": "heal_1", "meditate": "heal_1"}[slot]
        prefix = ICON_PREFIX[element]

        def ability(desc, select=None):
            return el(skill, "ability", manaCost=mana, healthCost=0, cooldown=cooldown, instant=False,
                      selectTarget=select, desc=desc)

        for value in SLOT_RANKS[slot]:
            if slot in ("basic", "strike", "blast", "fury", "storm"):
                lo, hi = value
                link_type = "physical" if slot == "basic" else element
                target = "enemyteam" if slot == "storm" else "enemy"
                whom = "every enemy curio" if slot == "storm" else "the enemy"
                node = ability(f"Deals *d*{lo}*d*-*d*{hi}*d* [{link_type}] damage to {whom}.")
                el(node, "action", type="healthdamage", minAmount=lo, maxAmount=hi, multiplier=1.0, source="self",
                   target=target, linkType=link_type, fx=fx)
            elif slot == "drain":
                lo, hi = value
                node = ability(f"Deals *d*{lo}*d*-*d*{hi}*d* [{element}] damage and heals itself for half of the damage dealt.")
                el(node, "action", type="healthdrain", minAmount=lo, maxAmount=hi, multiplier=0.5, source="self",
                   target="enemy", linkType=element, fx=fx)
            elif slot in ("mend", "rally"):
                lo, hi = value
                if slot == "mend":
                    node = ability(f"Heals a curio on your team for *h*{lo}*h*-*h*{hi}*h* health.", select="selfteam")
                    target = "select"
                else:
                    node = ability(f"Heals every curio on your team for *h*{lo}*h*-*h*{hi}*h* health.")
                    target = "selfteam"
                el(node, "action", type="healthheal", minAmount=lo, maxAmount=hi, multiplier=1.0, source="self",
                   target=target, linkType=element, fx=fx)
            elif slot in ("guard", "focus"):
                turns, effect = (GUARD_TURNS, "resistperc") if slot == "guard" else (FOCUS_TURNS, "critchance")
                what = "Takes ^{}%^ less damage".format(value) if slot == "guard" else "Raises critical hit chance by ^{}%^".format(value)
                node = ability(f"{what} for {turns} turns.")
                action = el(node, "action", type="none", minAmount=turns, maxAmount=turns, source="self", target="self", fx=fx)
                buff = el(action, "buff", name="Guarded" if slot == "guard" else "Focused",
                          desc=f"{what}.", type="positive", icon=f"{prefix}_Heal_1.png",
                          thumbnail=f"{prefix}_Heal_1.png", loadLocal=True)
                el(buff, "effect", type=effect, amount=value)
            elif slot in ("burn", "curse"):
                (lo, hi), (dot_lo, dot_hi) = value
                dot_type = "fire" if slot == "burn" else "dark"
                node = ability(f"Deals *d*{lo}*d*-*d*{hi}*d* [{dot_type}] damage, then *d*{dot_lo}*d*-*d*{dot_hi}*d* more at the start of each of the enemy's next {DOT_TURNS} turns.")
                el(node, "action", type="healthdamage", minAmount=lo, maxAmount=hi, multiplier=1.0, source="self",
                   target="enemy", linkType=dot_type, fx=fx)
                action = el(node, "action", type="none", minAmount=DOT_TURNS, maxAmount=DOT_TURNS, source="self", target="enemy")
                buff = el(action, "buff", name="Burning" if slot == "burn" else "Cursed",
                          desc="Takes damage at the start of each turn.", type="negative",
                          icon="Fire_Attack_1.png" if slot == "burn" else "Dark_Attack_1.png",
                          thumbnail="Fire_Attack_1.png" if slot == "burn" else "Dark_Attack_1.png", loadLocal=True)
                trigger = el(buff, "trigger", type="turnstart")
                el(trigger, "action", type="healthdamage", minAmount=dot_lo, maxAmount=dot_hi, multiplier=1.0,
                   source="self", target="self", linkType=dot_type, fx="fire_1" if slot == "burn" else "dark_1")
            elif slot == "shock":
                lo, hi = value
                node = ability(f"Deals *d*{lo}*d*-*d*{hi}*d* [electric] damage and ^stuns^ the enemy for {STUN_TURNS} turn.")
                el(node, "action", type="healthdamage", minAmount=lo, maxAmount=hi, multiplier=1.0, source="self",
                   target="enemy", linkType="electric", fx=fx)
                action = el(node, "action", type="none", minAmount=STUN_TURNS, maxAmount=STUN_TURNS, source="self", target="enemy")
                buff = el(action, "buff", name="Stunned", desc="Cannot act.", type="negative",
                          icon="Electric_Attack_2.png", thumbnail="Electric_Attack_2.png", loadLocal=True)
                el(buff, "effect", type="stun", amount=0)
            elif slot == "meditate":
                node = ability(f"Restores ^{value}^ mana.")
                el(node, "action", type="manachange", minAmount=value, maxAmount=value, source="self", target="self", fx=fx)
            else:
                raise ValueError(f"slot desconhecido {slot}")
        for used in skill.iter():
            if used.get("fx") and used.get("fx") not in self.fx_links:
                self.errors.append(f"skill {link}: fx inexistente {used.get('fx')}")
            for attr in ("icon", "thumbnail"):
                if used.tag == "buff":
                    self.need("assets/images/abilities/icon/" + used.get(attr), f"buff {used.get('name')}")

    def _found_in(self):
        found = {}
        for zone in C.ZONES:
            for node in zone["nodes"]:
                for battle in node["battles"]:
                    for asset, _level in battle["pets"]:
                        places = found.setdefault(asset, [])
                        if zone["name"] not in places:
                            places.append(zone["name"])
        return {asset: ", ".join(places) for asset, places in found.items()}

    def _pet(self, parent, s, kit, found_in):
        asset, rarity, element = s["asset"], s["rarity"], s["element"]
        info = C.RARITY_INFO[rarity]
        starter = asset == C.STARTER
        pet = el(parent, "pet", id=s["id"], name=s["name"], desc=s["description"], rarity=rarity, type=element,
                 costGold=0 if starter else info["cost_gold"], costCredits=0 if starter else info["cost_credits"],
                 sellGold=info["sell_gold"], sellCredits=0, size=1, exchangable=not starter, starter=starter,
                 visible=True, foundIn=found_in or "Curio Capsules", loadLocal=True)
        stats = self._stats(s)
        el(pet, "stats", **{f"{stat}{part}": value for stat, (base, gain) in stats.items()
                            for part, value in (("Base", base), ("Gain", gain))})
        skills = el(pet, "skills")
        for index, (link, slot, _element, name, icon) in enumerate(kit, start=1):
            tree = C.SKILL_TREE[index - 1]
            self.need("assets/images/abilities/icon/" + icon, f"skill {name}")
            el(skills, "skill", id=index, link=link, name=name, icon=icon, thumbnail=icon,
               xPos=tree["pos"][0], yPos=tree["pos"][1], startRank=1 if index <= 2 else 0, levelReq=tree["level"],
               skillsReq=",".join(str(req) for req in tree["requires"] if req <= len(kit)),
               rankCosts=",".join(str(cost) for cost in SLOT_RANK_COSTS[slot][:len(SLOT_RANKS[slot])]),
               required=slot == "basic", loadLocal=True)
        prestiges = el(pet, "prestiges")
        for prestige, suffix in enumerate(("", "_E1", "_E2")):
            prestiges.append(self._prestige(asset + suffix, prestige, rarity))

    def _stats(self, s):
        if s["asset"] in C.STAT_OVERRIDES:
            return dict(C.STAT_OVERRIDES[s["asset"]])
        stats = {}
        for stat, (base, gain) in C.RARITY_STATS[s["rarity"]].items():
            mult = 1.0
            if stat != "mana":
                digest = hashlib.md5(f"{s['asset']}:{stat}".encode()).digest()
                mult = C.ELEMENT_STATS[s["element"]][stat] * (0.95 + digest[0] / 2550)
            stats[stat] = (max(1, round(base * mult)), round(gain * mult))
        return stats

    def _prestige(self, base, prestige, rarity):
        found = {kind: self.apk.find(path) for kind, path in (
            ("thumbnail", f"assets/images/pets/thumbnail/{base}.png"),
            ("icon", f"assets/images/pets/icon/{base}.png"),
            ("image", f"assets/swfs/pets/{base}.swf"))}
        names = {kind: (path.rsplit("/", 1)[1] if path else None) for kind, path in found.items()}
        load_local = all(found.values()) or not self.apk.available
        if self.apk.available:
            if not found["image"]:
                self.errors.append(f"curio {base}: animacao ausente")
            for kind, other in (("icon", "thumbnail"), ("thumbnail", "icon")):
                if not found[kind] and found[other]:
                    names[kind] = names[other]
                    self.alias(f"assets/images/pets/{kind}/{names[kind]}", found[other])
                    self.warnings.append(f"curio {base}: {kind} ausente, usando {found[other]} via servidor")
        perc = C.PRESTIGE_PERC[prestige]
        node = ET.Element("prestige", {key: fmt(value) for key, value in dict(
            id=prestige, maxLevel=C.PRESTIGE_MAX_LEVEL[prestige], thumbnail=names["thumbnail"] or base + ".png",
            icon=names["icon"] or base + ".png", image=names["image"] or base + ".swf", loadLocal=load_local,
            offsetX=0, offsetY=0, healthPerc=perc, healthGain=0, manaPerc=0.0,
            manaGain=C.PRESTIGE2_MANA_GAIN[rarity] if prestige == 2 else 0, damagePerc=perc, damageGain=0,
            healingPerc=perc, healingGain=0, luckPerc=perc, luckGain=0).items()})
        return node

    # ---------------------------------------------------------------- economy
    def currency_book(self):
        root = el(self.book("CurrencyBook.xml"), "currencies")
        for cid, _link, name, desc, icon in C.CURRENCIES:
            el(root, "currency", id=cid, rarity="common", name=name, desc=desc, thumbnail=icon, icon=icon, loadLocal=False)
            for kind in ("icon", "thumbnail"):
                self.alias(f"assets/images/currency/{kind}/{icon}", "assets/images/prizewheel/icon/" + icon)

    def service_book(self):
        root = el(self.book("ServiceBook.xml"), "services")
        for sid, kind, name, desc, value, gold, credits, icon in C.SERVICES:
            el(root, "service", id=sid, rarity="common", name=name, desc=desc, thumbnail=icon, icon=icon,
               loadLocal=False, costGold=gold, costCredits=credits, type=kind, value=value, bonus="", bestValue=False,
               sellGold=0, sellCredits=0)
            for part in ("icon", "thumbnail"):
                self.alias(f"assets/images/services/{part}/{icon}", "assets/images/prizewheel/icon/" + icon)

    def grab_bag_book(self):
        root = self.book("GrabBagBook.xml")
        for bag in C.GRAB_BAGS:
            node = el(root, "grabbag", id=bag["id"], rarity=bag["rarity"], name=bag["name"], roll=bag["roll"],
                      desc=bag["desc"], thumbnail=bag["icon"], icon=bag["icon"], loadLocal=False,
                      costGold=bag["cost_gold"], costCredits=bag["cost_credits"], sellGold=0, sellCredits=0)
            for part in ("icon", "thumbnail"):
                self.alias(f"assets/images/grabbag/{part}/{bag['icon']}", "assets/images/prizewheel/icon/" + bag["icon"])
            items = el(node, "items")
            if bag["loot"] == "curios":
                for rarity, odds in C.CAPSULE_ODDS.items():
                    pool = [s for s in self.species if s["rarity"] == rarity and s["asset"] != C.STARTER]
                    for s in pool:
                        el(items, "item", id=s["id"], type="pet", qty=1, perc=round(odds / len(pool), 3))
            else:
                for kind, ref, qty, perc in bag["loot"]:
                    self.item(items, kind, ref, qty, perc=perc)

    def variable_book(self):
        root = self.book("VariableBook.xml")
        variables = el(root, "variables")
        for name, value in C.VARIABLES.items():
            el(variables, name, text=fmt(value))
        for name, value in C.NEW_PLAYER.items():
            el(variables, "newPlayer" + name.capitalize(), text=fmt(value))
        # Battle loot rides along in VariableBook: the client ignores elements it does not know,
        # and this keeps the drop table with the rest of the tuning instead of inventing a book.
        # (self.book must be called once and kept - a second call registers a fresh root and
        # throws away everything written above.)
        loot = el(root, "battleLoot")
        for level, drops in C.BATTLE_LOOT:
            tier = el(loot, "tier", level=level)
            for material_id, perc in drops:
                el(tier, "drop", id=material_id, perc=perc)

    def rank_and_fusion_books(self):
        ranks = el(self.book("PetRankBook.xml"), "ranks")
        # the dust sits on the rank the curio already holds: PetUpgradeRankPanel prices the next
        # rank with _currentRankRef.upgradeItemData, so the last rank is the one without a price
        for rid, (name, perc, dust) in enumerate((("Unranked", 0.0, 100), ("C", 0.1, 300), ("B", 0.2, 800),
                                                  ("A", 0.35, 2000), ("S", 0.5, 0))):
            el(ranks, "rank", id=rid, name=name, healthPerc=perc, healthGain=0, manaPerc=0.0, manaGain=0,
               damagePerc=perc, damageGain=0, healingPerc=perc, healingGain=0, luckPerc=perc, luckGain=0,
               itemID=C.CURRENCY_ID["dust"] if dust else None, itemType="currency" if dust else None,
               itemQty=dust or None, upgradeRank=rid + 1 if rid < 4 else -1)
        fusions = el(self.book("PetFusionBook.xml"), "fusions")
        for fid, (name, perc) in enumerate((("No Fusion", 0.0), ("Fusion I", 0.05), ("Fusion II", 0.1), ("Fusion III", 0.15))):
            el(fusions, "fusion", id=fid, name=name, desc=f"Fused with duplicate curios: +{int(perc * 100)}% stats.",
               loadLocal=False, healthPerc=perc, healthGain=0, manaPerc=0.0, manaGain=0, damagePerc=perc, damageGain=0,
               healingPerc=perc, healingGain=0, luckPerc=perc, luckGain=0, visible=fid > 0,
               upgradeDupes=fid + 1 if fid < 3 else -1, upgradeFusion=fid + 1 if fid < 3 else -1)

    # ---------------------------------------------------------------- story
    def dialog_book(self):
        dialogs = el(self.book("DialogBook.xml"), "dialogs")
        for link, frames in C.DIALOGS.items():
            dialog = el(dialogs, "dialog", link=link)
            frames_el = el(dialog, "frames")
            background = None
            for frame in frames:
                background = frame.get("bg", background)
                if background:
                    folder = "swfs/dialog/bg/" if background.endswith(".swf") else "images/dialog/bg/"
                    self.need("assets/" + folder + background, f"dialogo {link}")
                if "player" in frame:
                    for gender in ("male", "female"):
                        self.need(f"assets/images/character/{gender}/{frame['player']}", f"dialogo {link}")
                    attrs = dict(portrait=True, image=frame["player"], name="")
                else:
                    self.need("assets/images/dialog/" + frame["image"], f"dialogo {link}")
                    attrs = dict(portrait=False, image=frame["image"], name=frame["name"])
                el(frames_el, "frame", text=frame["text"], position=frame["pos"], bg=background or "",
                   loadLocal=True, **attrs)

    def zone_books(self):
        zone_book = self.book("ZoneBook.xml")
        zones_el = el(zone_book, "zones")
        for zone in C.ZONES:
            # zone art comes from the server, like the original CDN: loading it straight from
            # the app is so fast that the client's transition screen misses the "loaded" event
            # and stays on LOADING forever
            el(zones_el, "zone", id=zone["id"], xml=zone["xml"], loadLocal=False)
            self.need("assets/swfs/zones/" + zone["bg"], f"zona {zone['id']}")
            self.need("assets/images/zones/thumbnail/" + zone["thumbnail"], f"zona {zone['id']}")
            root = self.book(zone["xml"])
            zone_el = el(root, "zone", name=zone["name"], desc=zone["desc"], thumbnail=zone["thumbnail"],
                         zoneBG=zone["bg"], width=zone["width"], height=zone["height"], starter=zone["starter"],
                         requiredZones=",".join(map(str, zone["requires"])) or None)
            for dtype in ("story", "hard"):
                hard = dtype == "hard"
                difficulty = el(zone_el, "difficulty", type=dtype, requiredDifficulties="story" if hard else None)
                nodes_el = el(difficulty, "nodes")
                previous = None
                for index, node in enumerate(zone["nodes"]):
                    self._node(nodes_el, zone, node, hard, previous, zone["nodes"][index + 1] if index + 1 < len(zone["nodes"]) else None)
                    previous = node

    def _node(self, parent, zone, node, hard, previous, following):
        levels = [level + (C.HARD_LEVEL_BONUS if hard else 0) for battle in node["battles"] for _asset, level in battle["pets"]]
        self.need("assets/swfs/zones/nodes/" + node["asset"], f"no {node['name']}")
        self.need("assets/images/battle/" + node["bg"], f"no {node['name']}")
        node_el = el(parent, "node", id=node["id"], name=node["name"], desc=node["desc"], battleBG=node["bg"],
                     xPos=node["x"], yPos=node["y"], asset=node["asset"], energy=zone["id"] + (1 if hard else 0),
                     exp=5 + 2 * max(levels), completeZone=node.get("complete_zone", False), hidden=False,
                     unlockNodes=previous["id"] if previous else None, hitbox="-50,-50,100,100",
                     starsOffsetX=0, starsOffsetY=0, layer=0)
        battles = el(node_el, "battles")
        for index, battle in enumerate(node["battles"]):
            pet_levels = [level + (C.HARD_LEVEL_BONUS if hard else 0) for _asset, level in battle["pets"]]
            average = sum(pet_levels) / len(pet_levels)
            self.need("assets/images/dialog/" + battle["thumbnail"], f"batalha {battle['name']}")
            battle_el = el(battles, "battle", name=battle["name"], desc=battle["desc"], thumbnail=battle["thumbnail"],
                           # each win fills one point of the node's health bar, so the chain of fights
                           # advances one per victory; health 0 on the last fight makes the node
                           # repeatable forever (ZoneNodeRef.getCurrentBattleRef), which is how the
                           # game lets players farm gold and DNA on a node they already finished
                           loadLocal=True, health=0 if index == len(node["battles"]) - 1 else 1,
                           dialogEnter=None if hard else battle.get("enter"),
                           dialogVictory=None if hard else battle.get("victory"),
                           dialogDefeat=None if hard else C.DEFEAT_DIALOG,
                           gold=round((15 + 10 * average) * (1.5 if hard else 1)),
                           petExp=round(12 + 8 * average), dna=battle["dna"] // (2 if hard else 1))
            for link in (battle.get("enter"), battle.get("victory"), C.DEFEAT_DIALOG):
                if link and link not in C.DIALOGS:
                    self.errors.append(f"batalha {battle['name']}: dialogo inexistente {link}")
            pets = el(battle_el, "pets")
            for (asset, _level), level in zip(battle["pets"], pet_levels):
                if asset not in self.by_asset:
                    self.errors.append(f"batalha {battle['name']}: curio inexistente {asset}")
                    continue
                el(pets, "pet", id=self.by_asset[asset]["id"], level=level)
        if following:
            paths = el(node_el, "paths")
            el(paths, "path", node=following["id"], layer=0,
               points=f"{node['x']}:{node['y']},{following['x']}:{following['y']}")

    # ---------------------------------------------------------------- activities
    def plinko_book(self):
        root = self.book("PlinkoBook.xml")
        for position, loot in C.PLINKO:
            items = el(el(root, "plinko", id=position, position=position), "items")
            for kind, ref, qty, perc in loot:
                self.item(items, kind, ref, qty, perc=perc)

    def achievement_book(self):
        root = el(self.book("AchievementBook.xml"), "achievements")
        for aid, name, desc, icon, objective, target, track, amounts, (reward, qty) in C.ACHIEVEMENTS:
            self.need("assets/images/achievements/icon/" + icon, f"conquista {name}")
            node = el(root, "achievement", id=aid, name=name, desc=re.sub(r"\[(\w+)\]", lambda m: m.group(1).capitalize(), desc),
                      icon=icon, thumbnail=icon, objective=objective, target=target, loadLocal=True, track=track)
            ranks = el(node, "ranks")
            for rank, amount in enumerate(amounts):
                rewards = el(el(ranks, "rank", id=rank, amtNeeded=amount), "rewards")
                self.item(rewards, "currency", reward, qty * (rank + 1))

    def job_book(self):
        root = el(self.book("JobBook.xml"), "jobs")
        for jid, name, desc, icon, objective, count, target, pet_type, (reward, qty) in C.JOBS:
            node = el(root, "job", id=jid, name=name, desc=desc, thumbnail=icon, icon=icon, objective=objective,
                      count=count, target=target, petType=pet_type, loadLocal=False)
            for part in ("icon", "thumbnail"):
                self.alias(f"assets/images/jobs/{part}/{icon}", "assets/images/achievements/icon/" + icon)
            self.item(el(node, "rewards"), "currency", reward, qty)

    def shop_book(self):
        tabs = el(self.book("ShopBook.xml"), "tabs")
        for tab in C.SHOP_TABS:
            items = el(el(tabs, "tab", name=tab["name"], tutorial=False), "items")
            if tab["items"] == "curios":
                for s in sorted(self.species, key=lambda s: (C.RARITIES.index(s["rarity"]), s["name"])):
                    if s["asset"] != C.STARTER:
                        el(items, "item", id=s["id"], type="pet", desc=s["description"])
            else:
                for kind, ref, desc in tab["items"]:
                    el(items, "item", id=ref, type=kind, desc=desc)

    def daily_book(self):
        root = self.book("DailyBook.xml")
        for day, rewards in enumerate(C.DAILY_REWARDS):
            items = el(el(root, "daily", day=day), "items")
            for kind, ref, qty in rewards:
                self.item(items, kind, ref, qty)

    def prize_wheel_book(self):
        rewards = el(self.book("PrizeWheelBook.xml"), "spinRewards")
        for index, (icon, (kind, ref, qty), weight) in enumerate(C.PRIZE_WHEEL):
            self.need("assets/images/prizewheel/icon/" + icon, "roda de premios")
            item_id = C.CURRENCY_ID[ref] if kind == "currency" else ref
            el(rewards, "spinReward", id=index, icon=icon, loadLocal=True, itemType=kind, itemID=item_id, qty=qty, weight=weight)

    def success_book(self):
        root = self.book("SuccessBook.xml")
        for name, color, low, high in C.SUCCESS_RATES:
            el(root, "success", name=name, color=color, minPerc=low, maxPerc=high)

    def enchant_book(self):
        """EnchantBook reads <enchants><enchant>, with `slots` as comma-separated colour names."""
        root = el(self.book("EnchantBook.xml"), "enchants")
        for enchant in C.ENCHANTS:
            self.alias_item_art("enchantsnew", enchant["icon"])
            stats = enchant["stats"]
            el(root, "enchant", id=enchant["id"], rarity=enchant["rarity"], name=enchant["name"],
               desc=enchant["desc"], thumbnail=enchant["icon"], icon=enchant["icon"], loadLocal=False,
               costGold=0 if enchant["upgrade_id"] else C.ENCHANT_SHOP_GOLD, costCredits=0,
               sellGold=enchant["destroy_gold"], sellCredits=0,
               slots=enchant["slots"],
               health=stats.get("health"), mana=stats.get("mana"), damage=stats.get("damage"),
               healing=stats.get("healing"), luck=stats.get("luck"),
               destroyGold=enchant["destroy_gold"],
               upgradeGold=enchant["upgrade_gold"] or None,
               # points BACKWARDS: getUpgradeEnchant finds the enchant whose upgradeID is this id
               upgradeID=enchant["upgrade_id"])

    def craft_book(self):
        """CraftBook reads <tabs><tab> plus root-level <craft>, each with one <result> and <items>."""
        root = self.book("CraftBook.xml")
        tabs = el(root, "tabs")
        for tab_id, name in C.CRAFT_TABS:
            el(tabs, "tab", id=tab_id, name=name)
        for recipe in C.CRAFTS:
            node = el(root, "craft", id=recipe["id"], tab=recipe["tab"])
            kind, ref, qty = recipe["result"]
            el(node, "result", id=ref, type=kind, qty=qty)
            items = el(node, "items")
            for kind, ref, qty in recipe["items"]:
                self.item(items, kind, ref, qty)

    def welcome_pack_book(self):
        """WelcomePackBook.parseXML reads <welcomePack> straight off the root, with no container."""
        root = self.book("WelcomePackBook.xml")
        pack = C.WELCOME_PACK
        for part in ("icon", "thumbnail"):
            self.alias(f"assets/images/welcomePack/{part}/{pack['icon']}",
                       "assets/images/prizewheel/icon/" + pack["icon"])
        node = el(root, "welcomePack", id=pack["id"], rarity=pack["rarity"], name=pack["name"],
                  desc=pack["desc"], thumbnail=pack["icon"], icon=pack["icon"], loadLocal=False)
        items = el(node, "items")
        for kind, ref, qty in pack["items"]:
            self.item(items, kind, ref, qty)

    def skin_book(self):
        """One <skin> per alternate look, with a <prestige> for each evolution stage.

        SkinRef prefixes thumbnail/icon with PET_THUMBNAIL/PET_ICON and sends <prestige image>
        through PET_SWF, so every path here is a bare asset name borrowed from another curio.
        """
        root = el(self.book("SkinBook.xml"), "skins")
        for skin in C.SKINS:
            node = el(root, "skin", id=skin["id"], petID=skin["pet_id"], offsetX=0, offsetY=0,
                      rarity=skin["rarity"], name=skin["name"], desc=skin["desc"],
                      thumbnail=skin["art"] + ".png", icon=skin["art"] + ".png", loadLocal=False,
                      costGold=0, costCredits=0, sellGold=0, sellCredits=0)
            for prestige, suffix in enumerate(("", "_E1", "_E2")):
                asset = skin["art"] + suffix
                what = f"skin {skin['name']}"
                self.need(f"assets/swfs/pets/{asset}.swf", what)
                self.need(f"assets/images/pets/thumbnail/{asset}.png", what)
                # many curios ship no icon at all, so the icon borrows the thumbnail like the PetBook
                self.alias(f"assets/images/pets/icon/{asset}.png",
                           f"assets/images/pets/thumbnail/{asset}.png")
                el(node, "prestige", id=prestige, thumbnail=asset + ".png", icon=asset + ".png",
                   image=asset + ".swf", offsetX=0, offsetY=0, loadLocal=False)

    def alias_item_art(self, folder, icon):
        """Consumables and materials had no art in the APK, so both sizes borrow a prize wheel icon."""
        for part in ("icon", "thumbnail"):
            self.alias(f"assets/images/{folder}/{part}/{icon}", "assets/images/prizewheel/icon/" + icon)

    def consumable_book(self):
        root = el(self.book("ConsumableBook.xml"), "consumables")
        for c in C.CONSUMABLES:
            self.alias_item_art("consumables", c["icon"])
            node = el(root, "consumable", id=c["id"], rarity=c["rarity"], name=c["name"], desc=c["desc"],
                      thumbnail=c["icon"], icon=c["icon"], loadLocal=False,
                      costGold=c["cost_gold"], costCredits=c["cost_credits"],
                      sellGold=c["sell_gold"], sellCredits=0, useGold=c["use_gold"],
                      bonusTypes=",".join(c["bonus_types"]) or None)
            # <stat> is what any curio gains, bonus<Stat> what a curio of a bonusTypes element gains
            for stat, (normal, bonus) in c["stats"].items():
                node.set(stat, fmt(normal))
                node.set("bonus" + stat.capitalize(), fmt(bonus))

    def material_book(self):
        root = el(self.book("MaterialBook.xml"), "materials")
        for m in C.MATERIALS:
            self.alias_item_art("materials", m["icon"])
            el(root, "material", id=m["id"], rarity=m["rarity"], name=m["name"], desc=m["desc"],
               thumbnail=m["icon"], icon=m["icon"], loadLocal=False,
               costGold=m["cost_gold"], costCredits=m["cost_credits"],
               sellGold=m["sell_gold"], sellCredits=0)

    def video_offer_book(self):
        el(self.book("VideoOfferBook.xml"), "offer", id=1, name="Free Plasma", itemID=C.CURRENCY_ID["credits"],
           itemType="currency", duration=0)

    def guild_book(self):
        root = self.book("GuildBook.xml")
        levels = el(root, "levels")
        for level in range(1, 11):
            el(levels, "level", id=level, totalExp=500 * (level - 1) * level)
        el(root, "guildRep")
        el(root, "factionRep")

    def empty_books(self):
        containers = {
            "AchievementBook.xml": None, "ConsumableBook.xml": "consumables", "CraftBook.xml": "tabs",
            "EnchantBook.xml": "enchants", "FilterBook.xml": None, "FvFEventBook.xml": "events",
            "GvEEventBook.xml": "events", "GvGEventBook.xml": "events", "InAppBook.xml": None,
            "LimitedOfferBook.xml": None, "MarketingBook.xml": None, "MaterialBook.xml": "materials",
            "NewsBook.xml": None, "PetCollectionBook.xml": "collections", "PvEEventBook.xml": "events",
            "PvPEventBook.xml": "events", "ReferBook.xml": "rewards", "SkinBook.xml": "skins",
            "SocialBook.xml": "feedposts", "TimedModifierBook.xml": None, "WelcomePackBook.xml": None,
        }
        for name, container in containers.items():
            if name in self.books:
                continue
            root = self.book(name)
            if container:
                el(root, container)

    # ---------------------------------------------------------------- checks
    def validate_text(self):
        elements = set(C.ELEMENTS)
        for name, root in self.books.items():
            for node in root.iter():
                for where, text in [("texto", node.text or "")] + [(key, value) for key, value in node.attrib.items()
                                                                  if key in ("desc", "text", "name")]:
                    for link in re.findall(r"\[([^\]]*)\]", text):
                        if link.lower() not in elements:
                            self.errors.append(f"{name}: [{link}] nao e um elemento valido ({text[:60]})")
                    if text.count("[") != text.count("]") or text.count("^") % 2 or text.count("@") % 2:
                        self.errors.append(f"{name}: marcacao desbalanceada em {where}: {text[:60]}")
                    for pair in re.findall(r"@([^@]*)@", text):
                        if "/" not in pair:
                            self.errors.append(f"{name}: @...@ sem '/' em {where}: {text[:60]}")
        pet_links = {skill.get("link") for skill in self.books["PetBook.xml"].iter("skill")}
        for link in sorted(pet_links - self.skill_links):
            self.errors.append(f"PetBook usa skill inexistente {link}")
        currency_ids = {str(cid) for cid, *_ in C.CURRENCIES}
        bag_ids = {str(bag["id"]) for bag in C.GRAB_BAGS}
        service_ids = {str(service[0]) for service in C.SERVICES}
        pet_ids = {str(s["id"]) for s in self.species}
        consumable_ids = {str(c["id"]) for c in C.CONSUMABLES}
        material_ids = {str(m["id"]) for m in C.MATERIALS}
        enchant_ids = {str(e["id"]) for e in C.ENCHANTS}
        known = {"currency": currency_ids, "grabbag": bag_ids, "service": service_ids, "pet": pet_ids,
                 "consumable": consumable_ids, "material": material_ids, "enchant": enchant_ids}
        for name, root in self.books.items():
            for item in root.iter("item"):
                ids = known.get(item.get("type"))
                if ids is None or item.get("id") not in ids:
                    self.errors.append(f"{name}: item inexistente {item.attrib}")
        # Ordem de inicializacao: um livro da lista abaixo resolve os <item> filhos ali mesmo no
        # parseXML (ItemData.fromXml -> ItemBook.lookup).  Se o livro do tipo referenciado ainda
        # nao rodou, o lookup le .length de um Vector nulo -> TypeError #1009, que o AIR de
        # release engole: initBooks() para no meio e o cliente fica em LOADING para sempre.
        for name in BOOKS_RESOLVING_ITEMS:
            root = self.books.get(name)
            if root is None or name not in BOOK_INIT_ORDER:
                continue
            for item in root.iter("item"):
                target = ITEM_TYPE_BOOK.get(item.get("type"))
                if target and BOOK_INIT_ORDER.index(target) > BOOK_INIT_ORDER.index(name):
                    self.errors.append(
                        f"{name}: referencia adiantada para {target} em {item.attrib} - "
                        f"{target} so e inicializado depois, o cliente trava em LOADING")

    def write(self):
        if not self.local:
            # everything through the server: the HTTP log then shows how far the client got
            for root in self.books.values():
                for node in root.iter():
                    if "loadLocal" in node.attrib:
                        node.set("loadLocal", "false")
                    if node.tag == "characterLoadLocal":
                        node.text = "false"
        BOOKS_DIR.mkdir(parents=True, exist_ok=True)
        for old in BOOKS_DIR.glob("*.xml"):
            old.unlink()
        for name, root in sorted(self.books.items()):
            ET.indent(root, space="\t")
            data = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8") + b"\n"
            (BOOKS_DIR / name).write_bytes(data)
        ALIASES_PATH.write_text(json.dumps(dict(sorted(self.aliases.items())), indent=1), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apk", default=str(DEFAULT_APK))
    parser.add_argument("--no-local-assets", action="store_true",
                        help="carrega toda a arte pelo servidor (o log HTTP vira um rastro do que o jogo abriu)")
    args = parser.parse_args()
    builder = Builder(Apk(args.apk), local=not args.no_local_assets)
    builder.build()
    for warning in builder.warnings:
        print("aviso:", warning)
    if builder.errors:
        for error in builder.errors:
            print("ERRO:", error, file=sys.stderr)
        print(f"{len(builder.errors)} erro(s); nada foi gravado.", file=sys.stderr)
        return 1
    builder.write()
    print(f"{len(builder.books)} arquivos gravados em {BOOKS_DIR}")
    print(f"{len(builder.aliases)} aliases de assets em {ALIASES_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
