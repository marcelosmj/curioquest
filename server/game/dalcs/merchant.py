"""MerchantDALC (DALC_ID 3): buying curios and grab bags, and the services."""
import logging
import random

from ...es5.esobject import EsObject  # noqa: F401  (kept for the reply objects built here)
from ..dalc import Dalc, action
from ..keys import K
from .. import player as players
from .. import arcade, progress, rewards

log = logging.getLogger("merchant")

CRAFT = 1
BUY_SERVICE = 2
UPGRADE_ENCHANT = 5
DESTROY_ENCHANTS = 6
DAILY_SPIN = 3
PURCHASE_ITEM = 4
PLINKO = 7
WELCOME_PACK = 8
ROLL_CURIO = 9

# item types and the wallet mapping live in rewards.py, shared with the jobs and the achievements
ITEM_PET = rewards.ITEM_PET
ITEM_GRABBAG = rewards.ITEM_GRABBAG
TYPE_NAMES = rewards.TYPE_NAMES

# model.utility.ErrorCode
INVALID_PET = 7
INSUFFICIENT_FUNDS = 8
MAX_CAPACITY = 9
SERVICE_COOLDOWN = 24
INVALID_ITEM = 52

CURRENCY_GOLD = 1
CURRENCY_CREDITS = 2


class MerchantDalc(Dalc):
    dalc_id = 3
    name = "MerchantDALC"

    @action(WELCOME_PACK)
    async def welcome_pack(self, session, request):
        """Hand out the one-off starting pack.

        MenuScreen.checkWelcomePack fires this on EVERY menu open while
        character.getItemQty(pack) <= 0, so the grant has to include the pack item itself or the
        window reopens forever.  onWelcomePack reads nothing but ItemData.listFromEsObject(reply).
        """
        player = session.data.get("player")
        if player is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        data = self.game.data
        pack = next(iter(data.welcome_packs.values()), None)   # the client takes getFirstWelcomePack
        if pack is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        owned = next((item for item in player["inventory"]
                      if item["id"] == pack.id and item["type"] == rewards.ITEM_WELCOMEPACK), None)
        if owned and owned["qty"] > 0:
            log.info("[%d] pacote de boas-vindas ja resgatado", session.id)
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        granted = rewards.give_all(player, data, pack.items)
        rewards.give(player, data, pack.id, rewards.ITEM_WELCOMEPACK, 1)
        self.game.players.save(player)
        log.info("[%d] pacote de boas-vindas entregue (%d itens)", session.id, len(granted))
        return EsObject().set_esobject_array(K.ITEM_LIST, granted)

    @action(UPGRADE_ENCHANT)
    async def upgrade_enchant(self, session, request):
        """Upgrade a LOOSE enchant sitting in the bag.

        EnchantUpgradeWindow picks between two paths: with a curio and a socket it calls
        PetDALC.UPGRADE_ENCHANT (15), and without one it calls this, sending only ENCHANT_ID.
        onUpgradeEnchant then reads ITEM_REMOVED and ITEM_ADDED as ItemData objects - note the
        same ITEM_REMOVED key travels as a plain boolean in the other direction, on USE_ENCHANT.
        """
        player = session.data.get("player")
        if player is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        data = self.game.data
        current = data.enchants.get(int(request.get(K.ENCHANT_ID, 0)))
        better = data.upgrade_of(current.id) if current else None
        entry = next((item for item in player["inventory"]
                      if current and item["id"] == current.id
                      and item["type"] == rewards.ITEM_ENCHANT), None)
        if current is None or better is None or entry is None or entry["qty"] < 1:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        if player["gold"] < current.upgrade_gold:
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)

        player["gold"] -= current.upgrade_gold
        entry["qty"] -= 1
        removed = (EsObject().set_integer(K.ITEM_ID, current.id)
                   .set_integer(K.ITEM_TYPE, rewards.ITEM_ENCHANT).set_integer(K.ITEM_QTY, 1))
        added = rewards.give(player, data, better.id, rewards.ITEM_ENCHANT, 1)
        self.game.players.save(player)
        log.info("[%d] %s virou %s na bolsa", session.id, current.name, better.name)
        reply = EsObject().set_esobject(K.ITEM_REMOVED, removed).set_esobject(K.ITEM_ADDED, added)
        return self._wallet(reply, player)

    @action(DESTROY_ENCHANTS)
    async def destroy_enchants(self, session, request):
        """Crunch loose enchants down into gold.

        doDestroyEnchants sends ENCHANT_ID as an integer ARRAY (one entry per enchant, repeats
        allowed).  EnchantExchangeWindow.onCrunch takes the new CHARACTER_GOLD total - it works
        out the gain by subtracting what it held - and subtracts every ItemData in ITEM_LIST from
        the bag, so the list has to name what was actually destroyed, not what was asked for.
        """
        player = session.data.get("player")
        if player is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        data = self.game.data
        # doDestroyEnchants sends an integer ARRAY, but a single id arrives as a bare integer -
        # iterating that raises TypeError and the action dies without ever answering, which the
        # client reads as a hang.  Accept both shapes.
        pedido = request.get(K.ENCHANT_ID)
        if isinstance(pedido, (list, tuple)):
            wanted = [int(value) for value in pedido]
        elif pedido is None:
            wanted = []
        else:
            wanted = [int(pedido)]
        if not wanted:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)

        destroyed, earned = {}, 0
        for enchant_id in wanted:
            enchant = data.enchants.get(enchant_id)
            entry = next((item for item in player["inventory"]
                          if item["id"] == enchant_id and item["type"] == rewards.ITEM_ENCHANT), None)
            if enchant is None or entry is None or entry["qty"] < 1:
                continue                      # skip what the player does not hold, never fail the lot
            entry["qty"] -= 1
            destroyed[enchant_id] = destroyed.get(enchant_id, 0) + 1
            earned += enchant.destroy_gold
        if not destroyed:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)

        player["gold"] += earned
        self.game.players.save(player)
        log.info("[%d] destruiu %d encanto(s) por %d de ouro", session.id, sum(destroyed.values()), earned)
        reply = EsObject().set_esobject_array(K.ITEM_LIST, [
            EsObject().set_integer(K.ITEM_ID, enchant_id)
            .set_integer(K.ITEM_TYPE, rewards.ITEM_ENCHANT).set_integer(K.ITEM_QTY, qty)
            for enchant_id, qty in sorted(destroyed.items())])
        return self._wallet(reply, player)

    @action(CRAFT)
    async def craft(self, session, request):
        """Turn ingredients into an item.

        CraftTile.onCraft takes the consumed items from ITEM_LIST (it calls removeItem on each)
        and the crafted one from the ROOT of the reply, so the result goes flat, like ROLL_CURIO.
        isCraftable() is checked client-side too, but the bag is re-checked here: the client can
        be out of date and nothing else stops a stale tile from spending items twice.
        """
        player = session.data.get("player")
        if player is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        data = self.game.data
        recipe = data.crafts.get(int(request.get(K.CRAFT_ID, 0)))
        if recipe is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)

        held = {(item["id"], item["type"]): item for item in player["inventory"]}
        needed = [(item_id, rewards.type_id(kind), qty) for item_id, kind, qty in recipe.items]
        for item_id, type_id, qty in needed:
            entry = held.get((item_id, type_id))
            if entry is None or entry["qty"] < qty:
                return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)

        consumed = []
        for item_id, type_id, qty in needed:
            held[(item_id, type_id)]["qty"] -= qty
            consumed.append(EsObject().set_integer(K.ITEM_ID, item_id)
                            .set_integer(K.ITEM_TYPE, type_id).set_integer(K.ITEM_QTY, qty))
        result_id, result_kind, result_qty = recipe.result
        reply = rewards.give(player, data, result_id, result_kind, result_qty)
        reply.set_esobject_array(K.ITEM_LIST, consumed)
        self.game.players.save(player)
        log.info("[%d] forjou %s %d x%d", session.id, result_kind, result_id, result_qty)
        return reply

    @action(ROLL_CURIO)
    async def roll_curio(self, session, request):
        """The "Experimental Process": pay the curio's gold and roll against its DNA.

        doRollCurio sends NOTHING but the action - not even an id - so the species is the one the
        last won battle offered (battle.py stores it as pending_roll).  PetPurchaseWindow reads
        CHARACTER_GOLD and PET_ROLL_SUCCESS, plus a flat ItemData when it succeeds; the plasma
        button is a plain PURCHASE_ITEM, so there is no currency choice to make here.
        """
        player = session.data.get("player")
        if player is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        data = self.game.data
        species = data.species.get(int(player.get("pending_roll") or 0))
        if species is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        if not self._charge(player, species.cost_gold, 0):
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)

        dna = player.setdefault("dna", {})
        key = str(species.id)
        chance = int(dna.get(key, 0))
        success = random.randint(1, 100) <= chance
        dna[key] = 0                      # "You will lose the DNA of X" - win or lose
        player["pending_roll"] = 0
        # PetPurchaseWindow calls ItemData.fromEsObject on the WHOLE reply, so the curio's fields
        # have to sit on the root: build the reply out of what rewards.give already returns.
        reply = rewards.give(player, data, species.id, ITEM_PET) if success else EsObject()
        self._wallet(reply, player).set_boolean(K.PET_ROLL_SUCCESS, success)
        self.game.players.save(player)
        log.info("[%d] replicacao de %s com %d%%: %s", session.id, species.name, chance,
                 "sucesso" if success else "falhou")
        return reply

    @action(PURCHASE_ITEM)
    async def purchase_item(self, session, request):
        player = session.data.get("player")
        if player is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        data = self.game.data
        item_id = int(request.get(K.ITEM_ID, 0))
        item_type = int(request.get(K.ITEM_TYPE, 0))
        quantity = max(1, int(request.get(K.ITEM_QTY, 1)))
        # only what a shop tab actually lists can be bought, whatever the client asks for
        if (TYPE_NAMES.get(item_type, ""), item_id) not in data.shop_offers:
            log.warning("[%d] item fora da loja: tipo %s id %s", session.id, item_type, item_id)
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        if item_type == ITEM_PET:
            species = data.species.get(item_id)
            price = (species.cost_gold, species.cost_credits) if species else None
        elif item_type == ITEM_GRABBAG:
            bag = data.grab_bags.get(item_id)
            price = (bag.cost_gold, bag.cost_credits) if bag else None
        elif item_type == rewards.ITEM_CONSUMABLE:
            consumable = data.consumables.get(item_id)
            price = (consumable.cost_gold, consumable.cost_credits) if consumable else None
        elif item_type == rewards.ITEM_MATERIAL:
            material = data.materials.get(item_id)
            price = (material.cost_gold, material.cost_credits) if material else None
        elif item_type == rewards.ITEM_ENCHANT:
            enchant = data.enchants.get(item_id)
            price = (enchant.cost_gold, enchant.cost_credits) if enchant else None
        else:
            price = None
        if price is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        # doPurchaseItem sends CURRENCY_ID and the client picks ONE currency
        # (onPurchaseYes: costCredits > 0 ? CREDITS : GOLD).  Charging both, as this did before,
        # made every rare/epic/legendary curio unbuyable: they cost gold AND plasma in the book,
        # and a player with plenty of gold but little plasma was refused for "insufficient funds".
        moeda = int(request.get(K.CURRENCY_ID, 0)) or (CURRENCY_CREDITS if price[1] else CURRENCY_GOLD)
        if moeda == CURRENCY_CREDITS and price[1]:
            custo_ouro, custo_plasma = 0, price[1] * quantity
        elif price[0]:
            custo_ouro, custo_plasma = price[0] * quantity, 0
        else:
            custo_ouro, custo_plasma = 0, price[1] * quantity
        if not self._charge(player, custo_ouro, custo_plasma):
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)
        granted = []
        for _ in range(quantity):
            if item_type == ITEM_GRABBAG:
                granted += self._open_bag(player, data.grab_bags[item_id])
            else:
                # curios join the collection, consumables and materials land in the bag
                granted.append(rewards.give(player, data, item_id, item_type))
        log.info("[%d] comprou %s (tipo %d) x%d", session.id, item_id, item_type, quantity)
        self.game.push_progress(session, player)
        self.game.players.save(player)
        reply = (EsObject().set_integer(K.ITEM_ID, item_id).set_integer(K.ITEM_TYPE, item_type)
                 .set_integer(K.CURRENCY_ID, int(request.get(K.CURRENCY_ID, CURRENCY_GOLD))))
        reply.set_esobject_array(K.ITEM_LIST, granted)
        return self._wallet(reply, player)

    @action(BUY_SERVICE)
    async def buy_service(self, session, request):
        player = session.data.get("player")
        service = self.game.data.services.get(int(request.get(K.ITEM_ID, 0))) if player else None
        if service is None:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        extra = request.get(K.SERVICE_DATA)
        error = self._service_error(player, service, extra)
        if error:
            return EsObject().set_integer(K.ACTION_ERROR, error)
        if not self._charge(player, service.cost_gold, service.cost_credits):
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)
        reply = (EsObject().set_integer(K.ITEM_ID, service.id)
                 .set_integer(K.CURRENCY_ID, int(request.get(K.CURRENCY_ID, CURRENCY_CREDITS))))
        self._apply_service(player, service, extra, reply)
        log.info("[%d] comprou o servico '%s'", session.id, service.name)
        self.game.players.save(player)
        return self._wallet(reply, player)

    # ---------------------------------------------------------------- services
    def _service_error(self, player, service, extra):
        """Refuse before charging what ServiceSelectWindow would not even offer."""
        data = self.game.data
        if service.type == "teamslot" and player["teams_max"] + service.value > data.var("teamsMax", 5):
            return MAX_CAPACITY
        if service.type == "petmaxbonus" and player["pet_max_bonus"] + service.value > data.var("petBonusLimit", 400):
            return MAX_CAPACITY
        if service.type == "skillreset" and self._pet(player, extra) is None:
            return INVALID_PET
        if service.type == "name_change" and not str(extra or "").strip():
            return INVALID_ITEM
        return 0

    def _apply_service(self, player, service, extra, reply):
        """Each service type answers with the fields ServiceSelectWindow.executeService reads."""
        data = self.game.data
        if service.type in ("energy", "tickets", "tokens"):
            field = service.type
            countdowns = players.refill(player, data)
            maximum = data.var({"energy": "energyMax", "tickets": "ticketMax", "tokens": "tokenMax"}[field])
            player[field] = min(maximum, player[field] + service.value)
            milliseconds = 0.0 if player[field] >= maximum else countdowns.get(field, 0)
            keys = {"energy": (K.CHARACTER_ENERGY, K.CHARACTER_ENERGY_MILLISECONDS),
                    "tickets": (K.CHARACTER_TICKETS, K.CHARACTER_TICKET_MILLISECONDS),
                    "tokens": (K.CHARACTER_TOKENS, K.CHARACTER_TOKEN_MILLISECONDS)}[field]
            reply.set_integer(keys[0], player[field]).set_number(keys[1], milliseconds)
        elif service.type == "plinko":
            # ServiceSelectWindow.executeService plays the arcade at once with the balls just bought
            self._play_plinko(player, max(1, service.value), reply)
        elif service.type == "gold":
            player["gold"] += service.value
        elif service.type == "teamslot":
            player["teams_max"] += service.value
            reply.set_integer(K.CHARACTER_TEAMS_MAX, player["teams_max"])
        elif service.type == "petmaxbonus":
            player["pet_max_bonus"] += service.value
            reply.set_integer(K.CHARACTER_PET_MAX_BONUS, player["pet_max_bonus"])
        elif service.type == "skillreset":
            self._reset_skills(player, self._pet(player, extra), reply)
        elif service.type == "name_change":
            player["name"] = str(extra).strip()[:20]
            reply.set_string(K.CHARACTER_NAME, player["name"])

    def _reset_skills(self, player, pet, reply):
        """Give back every point spent and take the tree down to what the curio was born with."""
        species = self.game.data.species.get(pet["species"])
        refund = 0
        ranks = pet["skill_ranks"]
        for skill in species.skills if species else []:
            rank = ranks[skill.id] if skill.id < len(ranks) else 0
            for step in range(skill.start_rank, rank):
                refund += skill.rank_costs[step] if step < len(skill.rank_costs) else 0
            if skill.id < len(ranks):
                ranks[skill.id] = skill.start_rank
        pet["skill_points"] += refund
        slots = [sid if 0 < sid < len(ranks) and ranks[sid] > 0 else 0 for sid in pet["skill_slots"]]
        pet["skill_slots"] = slots
        (reply.set_integer(K.PET_UID, pet["uid"]).set_integer(K.PET_SKILL_POINTS, pet["skill_points"])
         .set_integer_array(K.PET_SKILL_RANKS, ranks).set_integer_array(K.PET_SKILL_SLOTS, slots))

    # ---------------------------------------------------------------- prize wheel
    @action(DAILY_SPIN)
    async def daily_spin(self, session, request):
        """Spin the wheel.  The server picks the slot; PrizeWheelScreen only lights it up."""
        player = session.data.get("player")
        data = self.game.data
        if player is None or not data.wheel:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        if player["num_free_spins"] > 0:
            player["num_free_spins"] -= 1
        elif player["num_spins"] > 0:
            player["num_spins"] -= 1
        else:
            return EsObject().set_integer(K.ACTION_ERROR, SERVICE_COOLDOWN)
        slot = random.choices(data.wheel, weights=[max(0, s.weight) for s in data.wheel])[0]
        if slot.item_type == "grabbag" and slot.item_id in data.grab_bags:
            # a bag on the wheel is opened at once, so the player is shown what they really won
            won = rewards.open_bag(player, data, data.grab_bags[slot.item_id])
            prize = won[0] if won else rewards.give(player, data, slot.item_id, slot.item_type, slot.qty)
        else:
            prize = rewards.give(player, data, slot.item_id, slot.item_type, slot.qty)
        progress.bump(player, "spins", 1)
        log.info("[%d] girou a roda: casa %d (%s %d x%d)", session.id, slot.id, slot.item_type,
                 slot.item_id, slot.qty)
        self.game.push_progress(session, player)
        self.game.players.save(player)
        # the prize object already carries the item (a whole curio, when it is one), so the wheel
        # fields go on top of it: PrizeWheelScreen reads the slot as 1-based and subtracts one
        return (prize.set_integer(K.WHEEL_SPIN_RESULT, slot.id + 1)
                .set_integer(K.CHARACTER_NUM_SPINS, player["num_spins"])
                .set_integer(K.CHARACTER_NUM_FREE_SPINS, player["num_free_spins"])
                .set_number(K.CHARACTER_SPIN_MILLISECONDS, 0.0))

    # ---------------------------------------------------------------- arcade
    @action(PLINKO)
    async def plinko(self, session, request):
        """Play the arcade: the balls are paid in tokens and the whole fall is simulated here."""
        player = session.data.get("player")
        data = self.game.data
        if player is None or not data.plinko:
            return EsObject().set_integer(K.ACTION_ERROR, INVALID_ITEM)
        balls = max(1, min(10, int(request.get(K.PLINKO_BALLS, 1))))
        field = rewards.CURRENCY_FIELDS.get(data.var("plinkoCostItemID", 8))
        price = balls * max(1, data.var("plinkoCostItemQty", 5))
        if field is None or player.get(field, 0) < price:
            return EsObject().set_integer(K.ACTION_ERROR, INSUFFICIENT_FUNDS)
        player[field] -= price
        reply = EsObject()
        self._play_plinko(player, balls, reply)
        self.game.push_progress(session, player,
                                progress.advance_jobs(player, data, "plinko", balls, target="self"))
        self.game.players.save(player)
        return reply

    def _play_plinko(self, player, balls, eso):
        """Drop the balls, pay what each slot holds and hand the client the whole animation."""
        data = self.game.data
        thrown, won = [], []
        for _ball in range(balls):
            slot = arcade.pick_slot()
            thrown.append(arcade.drop(slot))
            table = data.plinko.get(slot) or []
            weights = [max(0.0, item.perc) for item in table]
            if not table or sum(weights) <= 0:
                continue
            prize = random.choices(table, weights=weights)[0]
            if prize.type == "grabbag" and prize.id in data.grab_bags:
                won += rewards.open_bag(player, data, data.grab_bags[prize.id])
            else:
                won.append(rewards.give(player, data, prize.id, prize.type, prize.qty))
        progress.bump(player, "plinko", balls)
        log.info("jogou %d bola(s) no plinko e ganhou %d item(ns)", balls, len(won))
        eso.set_esobject_array(K.PLINKO_OBJECTS, arcade.board())
        eso.set_esobject_array(K.PLINKO_BALLS, thrown)
        eso.set_esobject_array(K.ITEM_LIST, won)

    # ---------------------------------------------------------------- items
    def _open_bag(self, player, bag):
        return rewards.open_bag(player, self.game.data, bag)

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _pet(player, uid):
        try:
            wanted = int(str(uid).strip())
        except (TypeError, ValueError):
            return None
        return next((pet for pet in player["pets"] if pet["uid"] == wanted), None)

    @staticmethod
    def _charge(player, gold, credits):
        if gold > player["gold"] or credits > player["credits"]:
            return False
        player["gold"] -= gold
        player["credits"] -= credits
        return True

    @staticmethod
    def _wallet(reply, player):
        return reply.set_integer(K.CHARACTER_GOLD, player["gold"]).set_integer(K.CHARACTER_CREDITS, player["credits"])
