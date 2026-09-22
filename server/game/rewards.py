"""Handing out items, shared by the shop, the jobs and the achievements.

Every payout the client understands is an ItemData in an ITEM_LIST: a curio joins the collection,
a currency lands in the wallet (exactly as model.character.Character.addItem credits it on the
client, so both sides agree after a relog) and anything else goes to the bag of items.
"""
import random

from ..es5.esobject import EsObject
from .keys import K
from . import player as players

# model.item.ItemRef
ITEM_PET = 1
ITEM_MATERIAL = 2
ITEM_CURRENCY = 3
ITEM_SERVICE = 4
ITEM_CONSUMABLE = 5
ITEM_GRABBAG = 6
ITEM_SKIN = 7
ITEM_ENCHANT = 8
ITEM_STARTERPACK = 9
ITEM_WELCOMEPACK = 10
ITEM_TIMED_MODIFIER = 11
ITEM_SHARD = 12
# the whole ItemRef table, not just the types we hand out today: an unknown name falls back to
# ITEM_MATERIAL, which used to turn a granted skin into a material without a word of warning
TYPE_IDS = {"pet": ITEM_PET, "material": ITEM_MATERIAL, "currency": ITEM_CURRENCY,
            "service": ITEM_SERVICE, "consumable": ITEM_CONSUMABLE, "grabbag": ITEM_GRABBAG,
            "skin": ITEM_SKIN, "enchant": ITEM_ENCHANT, "starterpack": ITEM_STARTERPACK,
            "welcomepack": ITEM_WELCOMEPACK, "timedmodifier": ITEM_TIMED_MODIFIER, "shard": ITEM_SHARD}
TYPE_NAMES = {value: name for name, value in TYPE_IDS.items()}

# CurrencyBook id -> the save field that holds it (spins land on numSpins, like the client)
CURRENCY_FIELDS = {1: "gold", 2: "credits", 3: "bps", 4: "exp", 5: "dust", 6: "energy",
                   7: "num_spins", 8: "tokens", 9: "tickets"}


def type_id(name):
    return TYPE_IDS.get(str(name).lower(), ITEM_MATERIAL)


def give(player, data, item_id, item_type, quantity=1):
    """Give one reward and answer with the ItemData entry the client shows for it."""
    if isinstance(item_type, str):
        item_type = type_id(item_type)
    if item_type == ITEM_PET and item_id in data.species:
        pet = players.add_pet(player, data, item_id)
        return (players.pet_esobject(pet).set_integer(K.ITEM_ID, item_id)
                .set_integer(K.ITEM_TYPE, ITEM_PET).set_integer(K.ITEM_QTY, 1))
    if item_type == ITEM_CURRENCY and item_id in CURRENCY_FIELDS:
        field = CURRENCY_FIELDS[item_id]
        player[field] = player.get(field, 0) + quantity
        return _entry(item_id, ITEM_CURRENCY, quantity)
    return _inventory(player, item_id, item_type, quantity)


def give_all(player, data, rewards):
    """rewards: (item id, item type, quantity) as the books write them."""
    return [give(player, data, item_id, item_type, quantity) for item_id, item_type, quantity in rewards]


def open_bag(player, data, bag):
    """Roll a grab bag's table as many times as it says and give what came out."""
    weights = [max(0.0, item.perc) for item in bag.items]
    if not bag.items or sum(weights) <= 0:
        return []
    rolled = [random.choices(bag.items, weights=weights)[0] for _ in range(bag.roll)]
    return [give(player, data, item.id, item.type, item.qty) for item in rolled]


def _inventory(player, item_id, item_type, quantity):
    entry = next((i for i in player["inventory"] if i["id"] == item_id and i["type"] == item_type), None)
    if entry is None:
        entry = {"id": item_id, "type": item_type, "qty": 0}
        player["inventory"].append(entry)
    entry["qty"] += quantity
    return _entry(item_id, item_type, quantity)


def _entry(item_id, item_type, quantity):
    return (EsObject().set_integer(K.ITEM_ID, item_id).set_integer(K.ITEM_TYPE, item_type)
            .set_integer(K.ITEM_QTY, quantity).set_integer(K.PET_PRESTIGE, 0).set_integer(K.PET_SKIN, 0))
