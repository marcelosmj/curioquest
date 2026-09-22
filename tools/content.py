"""Authored content for the Curio Quest offline revival.

The original numbers, story text and balance lived on 5th Planet's servers and are
lost, so everything in this file was re-created for the revival (curio names and
descriptions come from the Curio Quest Wiki where it had them).  Edit freely, then
rebuild the game data with:

    python tools/build_books.py

Text markup understood by the game client:
    ^text^          green highlight
    [fire]          element name in yellow (must be a real element link!)
    %name%          the player's name
    @boy/girl@      picks by the player's gender
    *d*120*d*       120% of the curio's damage (skill descriptions only)
    *h*150*h*       150% of the curio's healing (skill descriptions only)
Never use square brackets for anything other than element links: the client crashes.
"""

ELEMENTS = ("physical", "air", "earth", "light", "dark", "electric", "water", "fire")

ELEMENT_NAMES = {e: e.capitalize() for e in ELEMENTS}

# Element wheel: attacker -> defenders it is strong against.
# The reverse direction (defender attacking back) is weak.
STRONG_AGAINST = {
    "water": ("fire",),
    "fire": ("air",),
    "air": ("earth",),
    "earth": ("electric",),
    "electric": ("water",),
    "light": ("dark",),
    "dark": ("light",),
}
STRONG_MULTIPLIER = 0.5    # +50% damage
WEAK_MULTIPLIER = -0.3     # -30% damage

RARITIES = ("common", "rare", "epic", "legendary", "mythic")

# Core pieces a curio of each rarity is worth when exchanged.  PetExchangeWindow sums
# exchangeEpicCorePieces / exchangeLegendaryCorePieces / exchangeMythicCorePieces off the
# RarityBook, and those pieces are the only feed for rarity promotion - without them the
# exchange pays experience alone and promotion has no input at all.
RARITY_CORE_PIECES = {
    "common":    (0, 0, 0),
    "rare":      (1, 0, 0),
    "epic":      (3, 1, 0),
    "legendary": (6, 3, 1),
    "mythic":    (10, 6, 3),
}

# Cost of raising a curio one rarity (promotion) and of summoning one from shards.
# RarityPetOverrides walks the <rarityOverride>'s CHILDREN in order, so the position is the
# rarity - entry 0 is common, 1 rare, and so on - and each child carries promotionShards,
# summonShards, promotionGoldCost and summonGoldCost.  The element name is never read.
# Sized against what a fight actually pays: a won node battle drops a shard 35% of the time
# plus whatever DNA overflows past 100%, so roughly one shard every three wins.  The first
# promotion therefore costs about thirty fights - a real goal, not the eighty the first draft
# of this table implied, which would have made rarity promotion another dead system.
RARITY_PROMOTION = [
    # rarity, shards to promote INTO it, gold to promote, shards to summon, gold to summon
    ("common",     0,     0,   0,     0),
    ("rare",      10,  1500,  20,  3000),
    ("epic",      25,  5000,  50, 10000),
    ("legendary", 50, 15000, 100, 30000),
    ("mythic",   100, 40000, 200, 80000),
]

RARITY_INFO = {
    # color, evolve gold (prestige 1, 2), shop price, sell gold, exchange exp, bonus caps
    # cost_gold is also what the DNA replication charges (PetPurchaseWindow bills _petRef.costGold),
    # so it has to stay within reach of a new player: the very first node offers to replicate a
    # common curio, and at the old 1500 that button could never be pressed.
    "common":    {"name": "Common",    "color": "FFFFFF", "prestige_gold": (500, 2500),    "cost_gold": 400,   "cost_credits": 0,    "sell_gold": 100,   "exchange_exp": 50},
    "rare":      {"name": "Rare",      "color": "33B5FF", "prestige_gold": (1000, 5000),   "cost_gold": 2000,  "cost_credits": 60,   "sell_gold": 500,   "exchange_exp": 150},
    "epic":      {"name": "Epic",      "color": "C066FF", "prestige_gold": (2500, 12500),  "cost_gold": 0,     "cost_credits": 180,  "sell_gold": 2000,  "exchange_exp": 500},
    "legendary": {"name": "Legendary", "color": "FF9900", "prestige_gold": (5000, 25000),  "cost_gold": 0,     "cost_credits": 450,  "sell_gold": 5000,  "exchange_exp": 1500},
    "mythic":    {"name": "Mythic",    "color": "FF3B5C", "prestige_gold": (10000, 50000), "cost_gold": 0,     "cost_credits": 1000, "sell_gold": 10000, "exchange_exp": 5000},
}

# Level-1 stat and per-level gain by rarity: (base, gain).  Prestige 1 (level 10) gives
# +40% and prestige 2 (level 25) +75%, which reproduces the wiki's Ducan table exactly.
RARITY_STATS = {
    "common":    {"health": (290, 40),  "damage": (38, 7),  "healing": (80, 6),  "luck": (2, 1),  "mana": (10, 0)},
    "rare":      {"health": (250, 60),  "damage": (50, 9),  "healing": (75, 9),  "luck": (5, 1),  "mana": (10, 0)},
    "epic":      {"health": (400, 88),  "damage": (84, 12), "healing": (75, 12), "luck": (24, 1), "mana": (15, 0)},
    "legendary": {"health": (500, 104), "damage": (100, 16), "healing": (100, 14), "luck": (18, 1), "mana": (17, 0)},
    "mythic":    {"health": (700, 187), "damage": (130, 20), "healing": (110, 14), "luck": (38, 1), "mana": (24, 0)},
}
PRESTIGE_MAX_LEVEL = (10, 25, 40)
PRESTIGE_PERC = (0.0, 0.4, 0.75)
PRESTIGE2_MANA_GAIN = {"common": 0, "rare": 1, "epic": 2, "legendary": 2, "mythic": 3}

# Element flavour: multipliers on health / damage / healing / luck.
ELEMENT_STATS = {
    "physical": {"health": 1.10, "damage": 1.05, "healing": 0.85, "luck": 1.0},
    "air":      {"health": 0.95, "damage": 1.05, "healing": 1.00, "luck": 1.3},
    "earth":    {"health": 1.15, "damage": 0.95, "healing": 0.95, "luck": 0.9},
    "light":    {"health": 0.95, "damage": 0.95, "healing": 1.20, "luck": 1.0},
    "dark":     {"health": 0.95, "damage": 1.15, "healing": 0.85, "luck": 1.1},
    "electric": {"health": 0.95, "damage": 1.10, "healing": 0.95, "luck": 1.1},
    "water":    {"health": 1.00, "damage": 0.95, "healing": 1.10, "luck": 1.0},
    "fire":     {"health": 0.90, "damage": 1.20, "healing": 0.85, "luck": 1.0},
}

# Exact stats known from the wiki (level-1 base, per-level gain).
STAT_OVERRIDES = {
    "Duck":      {"health": (250, 60), "damage": (50, 9), "healing": (75, 9), "luck": (5, 1), "mana": (10, 0)},
    "Hydra":     {"health": (250, 60), "damage": (55, 9), "healing": (55, 9), "luck": (10, 0), "mana": (13, 0)},
    "Jellyfish": {"health": (283, 40), "damage": (41, 7), "healing": (76, 6), "luck": (1, 1), "mana": (10, 0)},
    "GummiBear": {"health": (304, 40), "damage": (32, 7), "healing": (85, 6), "luck": (1, 1), "mana": (10, 0)},
}

STARTER = "Duck"

# --------------------------------------------------------------------------------------
# Skills
# --------------------------------------------------------------------------------------

# Basic attack per curio: (skill link, name, icon).  Basic attacks deal physical damage.
BASIC_ATTACKS = {
    "AcidDog": ("basic_claw", "Bite", "Physical_Bite.png"),
    "AirHog": ("basic_impact", "Tackle", "Physical_Stomp.png"),
    "AirParrot": ("basic_claw", "Peck", "Physical_Bite.png"),
    "Anglerfish": ("basic_claw", "Bite", "Physical_Bite.png"),
    "Ant": ("basic_claw", "Pinch", "Physical_Scratch.png"),
    "Armordillo": ("basic_impact", "Roll Out", "Physical_Stomp.png"),
    "Bacteria": ("basic_impact", "Slap", "Physical_Punch.png"),
    "Bat": ("basic_claw", "Bite", "Physical_Bite.png"),
    "Bonsai": ("basic_impact", "Stomp", "Physical_Stomp.png"),
    "BulbBee": ("basic_claw", "Sting", "Physical_Scratch.png"),
    "CapnSkelly": ("basic_blade", "Cutlass", "Physical_Slash.png"),
    "Coconut": ("basic_impact", "Headbutt", "Physical_Punch.png"),
    "Dragon": ("basic_claw", "Scratch", "Physical_Scratch.png"),
    "Driftdeer": ("basic_impact", "Ram", "Physical_Stomp.png"),
    "Duck": ("basic_impact", "Slap", "Physical_Punch.png"),
    "EarthBomb": ("basic_impact", "Stomp", "Physical_Stomp.png"),
    "Fairy": ("basic_impact", "Slap", "Physical_Punch.png"),
    "FireCrab": ("basic_blade", "Pinch", "Physical_Slash.png"),
    "FireImp": ("basic_claw", "Scratch", "Physical_Scratch.png"),
    "Flower": ("basic_blade", "Thorn", "Physical_Slash.png"),
    "FrogPrince": ("basic_impact", "Slap", "Physical_Punch.png"),
    "Gecko": ("basic_claw", "Bite", "Physical_Bite.png"),
    "Gryphon": ("basic_claw", "Talon", "Physical_Scratch.png"),
    "GummiBear": ("basic_impact", "Slap", "Physical_Punch.png"),
    "Hydra": ("basic_claw", "Bite", "Physical_Bite.png"),
    "IceVulture": ("basic_claw", "Peck", "Physical_Bite.png"),
    "Jack": ("basic_blade", "Slash", "Physical_Slash.png"),
    "Jellyfish": ("basic_impact", "Slap", "Physical_Punch.png"),
    "Liger": ("basic_claw", "Maul", "Physical_Scratch.png"),
    "Magmo": ("basic_impact", "Smash", "Physical_Punch.png"),
    "Mantis": ("basic_blade", "Slash", "Physical_Slash.png"),
    "MiniYeti": ("basic_impact", "Punch", "Physical_Punch.png"),
    "Pelican": ("basic_claw", "Peck", "Physical_Bite.png"),
    "Penguin": ("basic_impact", "Slap", "Physical_Punch.png"),
    "PirateShark": ("basic_claw", "Chomp", "Physical_Bite.png"),
    "PlantRock": ("basic_impact", "Stomp", "Physical_Stomp.png"),
    "PlantToad": ("basic_impact", "Tongue Lash", "Physical_Punch.png"),
    "PrismGuy": ("basic_impact", "Punch", "Physical_Punch.png"),
    "Puppet": ("basic_impact", "Punch", "Physical_Punch.png"),
    "RockLobster": ("basic_blade", "Pinch", "Physical_Slash.png"),
    "Shadow": ("basic_claw", "Scratch", "Physical_Scratch.png"),
    "ThunderBird": ("basic_claw", "Peck", "Physical_Bite.png"),
    "TikiMask": ("basic_impact", "Headbutt", "Physical_Punch.png"),
    "Turnip": ("basic_claw", "Bite", "Physical_Bite.png"),
    "Turtle": ("basic_impact", "Stomp", "Physical_Stomp.png"),
    "WormApple": ("basic_claw", "Bite", "Physical_Bite.png"),
}

# Skill "slots" every element can have, with default names per element.
SKILL_NAMES = {
    "physical": {"strike": "Tackle", "blast": "Body Slam", "storm": "Rampage", "fury": "Crushing Blow",
                 "guard": "Thick Hide", "mend": "First Aid", "meditate": "Deep Breath"},
    "air": {"strike": "Gust", "blast": "Air Slash", "storm": "Tornado", "fury": "Sky Dive",
            "focus": "Tailwind", "mend": "Fresh Breeze"},
    "earth": {"strike": "Vine Whip", "blast": "Rock Slide", "storm": "Earthquake", "fury": "Boulder Crush",
              "guard": "Bark Skin", "mend": "Photosynthesis"},
    "light": {"strike": "Flash", "blast": "Sunbeam", "storm": "Radiance", "fury": "Holy Lance",
              "mend": "Soothe", "rally": "Blessing"},
    "dark": {"strike": "Shadow Claw", "blast": "Dark Pulse", "storm": "Nightfall", "fury": "Dark Blast",
             "drain": "Life Leech", "curse": "Curse"},
    "electric": {"strike": "Zap", "blast": "Thunderbolt", "storm": "Chain Lightning", "fury": "Overload",
                 "shock": "Static Shock", "mend": "Recharge", "focus": "Target Lock"},
    "water": {"strike": "Splash", "blast": "Water Jet", "storm": "Tidal Wave", "fury": "Aqua Impale",
              "mend": "Healing Rain", "drain": "Undertow"},
    "fire": {"strike": "Ember", "blast": "Fireball", "storm": "Inferno", "fury": "Flame Strike",
             "burn": "Scorch", "focus": "Kindle"},
}

ROLE_SKILL = {"physical": "guard", "air": "focus", "earth": "guard", "light": "mend",
              "dark": "drain", "electric": "shock", "water": "mend", "fire": "burn"}
EXTRA_SKILL = {"physical": "meditate", "air": "mend", "earth": "mend", "light": "rally",
               "dark": "curse", "electric": "focus", "water": "drain", "fire": "focus"}

KITS = {
    "common": ("basic", "strike", "role", "blast", "storm"),
    "rare": ("basic", "strike", "role", "blast", "fury"),
    "epic": ("basic", "strike", "role", "blast", "storm", "fury"),
    "legendary": ("basic", "strike", "role", "blast", "storm", "fury", "extra"),
    "mythic": ("basic", "strike", "role", "blast", "storm", "fury", "extra"),
}

# Skill lists taken from the wiki (slot, name), in the order the game showed them.
KIT_OVERRIDES = {
    "Hydra": (("basic", "Bite"), ("blast", "Harpoon"), ("strike", "Splash"), ("fury", "Aqua Impale"), ("storm", "Tidal Wave")),
    "Jellyfish": (("basic", "Slap"), ("strike", "Buzz"), ("mend", "Sprinkle"), ("shock", "Zap Wrap"), ("blast", "Jellotacle")),
    "GummiBear": (("basic", "Slap"), ("strike", "Bear Hug"), ("guard", "Hibernate"), ("mend", "Berry Juice"), ("blast", "Gumshoe")),
}

# Skill tree: position, level requirement and prerequisite (by position in the kit).
SKILL_TREE = (
    {"pos": (0, 0), "level": 1, "requires": ()},
    {"pos": (120, 0), "level": 1, "requires": ()},
    {"pos": (0, 110), "level": 5, "requires": (1,)},
    {"pos": (120, 110), "level": 8, "requires": (2,)},
    {"pos": (60, 220), "level": 15, "requires": (3, 4)},
    {"pos": (240, 110), "level": 20, "requires": (2,)},
    {"pos": (240, 220), "level": 30, "requires": (6,)},
)

# --------------------------------------------------------------------------------------
# Zones.  Pets are (curio asset, level).  "dna" is the chance, in percent, that a
# defeated wild curio offers to join.  Coordinates are in background pixels.
# --------------------------------------------------------------------------------------

ZONES = [
    {
        "id": 1, "xml": "Zone1.xml", "name": "Home Island",
        "desc": "A quiet island of old stones, treehouses and sandy beaches... until the Legion arrived.",
        "thumbnail": "Zone_1.png", "bg": "Zone_1_Background.swf", "width": 2400, "height": 480, "starter": True,
        "requires": [], "found_in": "Home Island",
        "nodes": [
            {"id": 1, "name": "Stone Circle", "desc": "Wild curios have gathered around the ancient stones next to your house.",
             "asset": "Zone_1_Flag.swf", "x": 470, "y": 330, "bg": "Stonehenge.jpg",
             "battles": [{"name": "Wild Curios", "desc": "Safari Sam wants to see your Ducan in action.",
                          "thumbnail": "SafariDude.png", "pets": [("FireImp", 1)], "dna": 35,
                          "enter": "z1n1_enter", "victory": "z1n1_win"}]},
            {"id": 2, "name": "Old Bridge", "desc": "Jace guards the old stone bridge and won't let anyone pass.",
             "asset": "Zone_1_Crate.swf", "x": 800, "y": 300, "bg": "GuardTower.jpg",
             "battles": [{"name": "Jace", "desc": "The bridge bully.", "thumbnail": "Jace.png",
                          "pets": [("AirHog", 2), ("Flower", 2)], "dna": 25,
                          "enter": "z1n2_enter", "victory": "z1n2_win"}]},
            {"id": 3, "name": "Treehouse", "desc": "The birds nesting in the old treehouse don't like visitors.",
             "asset": "Zone_1_Birds.swf", "x": 1010, "y": 175, "bg": "Treehouse.jpg",
             "battles": [{"name": "Nesting Curios", "desc": "Lee warned you about these.", "thumbnail": "Lee.png",
                          "pets": [("Bat", 3), ("Fairy", 3)], "dna": 25, "enter": "z1n3_enter"}]},
            {"id": 4, "name": "Jungle Generator", "desc": "The generator that powers the island, guarded by Jeff.",
             "asset": "Zone_1_Generator.swf", "x": 1330, "y": 280, "bg": "Island.jpg",
             "battles": [{"name": "Jeff", "desc": "He takes his job very seriously.", "thumbnail": "Jeff.png",
                          "pets": [("Bacteria", 4), ("Jellyfish", 4)], "dna": 20, "enter": "z1n4_enter"}]},
            {"id": 5, "name": "Treasure Beach", "desc": "Pirates are digging for treasure on the beach.",
             "asset": "Zone_1_Shovel.swf", "x": 1800, "y": 365, "bg": "Beach.jpg",
             "battles": [{"name": "Pirate Diggers", "desc": "They really want that treasure.", "thumbnail": "Pirate.png",
                          "pets": [("FireCrab", 5), ("Penguin", 5), ("FrogPrince", 5)], "dna": 20,
                          "enter": "z1n5_enter"}]},
            {"id": 6, "name": "The Dock", "desc": "The pirate ship is moored at the old dock. The Hermit waits nearby.",
             "asset": "Zone_1_Ship.swf", "x": 2100, "y": 250, "bg": "Ship.jpg", "complete_zone": True,
             "battles": [{"name": "Pirate Crew", "desc": "The captain's loyal crew.", "thumbnail": "Pirate.png",
                          "pets": [("FireImp", 6), ("Ant", 6)], "dna": 20, "enter": "z1n6a_enter"},
                         {"name": "Captain Blackfin", "desc": "The fearsome captain of the pirate ship.",
                          "thumbnail": "PirateCaptain.png", "pets": [("Ant", 6), ("FireImp", 7), ("TikiMask", 7)],
                          "dna": 15, "enter": "z1n6b_enter", "victory": "z1n6_win"}]},
        ],
    },
    {
        "id": 2, "xml": "Zone2.xml", "name": "Open Sea",
        "desc": "Endless water, strange weather and something huge swimming below the waves.",
        "thumbnail": "Zone_2.png", "bg": "Zone_2_Background.swf", "width": 1430, "height": 480, "starter": False,
        "requires": [1], "found_in": "Open Sea",
        "nodes": [
            {"id": 1, "name": "Sunny Shore", "desc": "The last stretch of sand before the open water.",
             "asset": "Zone_2_Umbrella.swf", "x": 100, "y": 300, "bg": "Beach.jpg",
             "battles": [{"name": "Beach Birds", "desc": "They want your sandwich.", "thumbnail": "Hermit.png",
                          "pets": [("Pelican", 7), ("IceVulture", 7)], "dna": 20, "enter": "z2n1_enter"}]},
            {"id": 2, "name": "Floating Tube", "desc": "Something is splashing around a lost inner tube.",
             "asset": "Zone_2_Tube.swf", "x": 265, "y": 390, "bg": "Beach.jpg",
             "battles": [{"name": "Splashers", "desc": "Wild water curios.", "thumbnail": "SafariDude.png",
                          "pets": [("Penguin", 8), ("FrogPrince", 8), ("Jellyfish", 8)], "dna": 20}]},
            {"id": 3, "name": "Giant Clam", "desc": "A clam the size of a house. Is that a pearl inside?",
             "asset": "Zone_2_Clam.swf", "x": 480, "y": 420, "bg": "Island.jpg",
             "battles": [{"name": "Deep Dwellers", "desc": "Curios from the bottom of the sea.", "thumbnail": "Pirate.png",
                          "pets": [("Anglerfish", 9), ("Jellyfish", 9)], "dna": 15}]},
            {"id": 4, "name": "Pirate Submarine", "desc": "The pirates are following you... from below.",
             "asset": "Zone_2_Submarine.swf", "x": 640, "y": 290, "bg": "SeaMonster.jpg",
             "battles": [{"name": "Submarine Crew", "desc": "Something big is coming.", "thumbnail": "Pirate.png",
                          "pets": [("Hydra", 10), ("Penguin", 10)], "dna": 15, "enter": "z2n4_enter"}]},
            {"id": 5, "name": "Monster's Belly", "desc": "Swallowed whole! Find a way out.",
             "asset": "Zone_2_Flag.swf", "x": 940, "y": 125, "bg": "Stomach.jpg",
             "battles": [{"name": "Belly Bugs", "desc": "Curios that live inside the sea monster.", "thumbnail": "Hermit.png",
                          "pets": [("Bacteria", 11), ("WormApple", 11), ("Turnip", 11)], "dna": 15,
                          "enter": "z2n5_enter"}]},
            {"id": 6, "name": "Bonfire Island", "desc": "A tiny island with a big bonfire and a party of fire curios.",
             "asset": "Zone_2_Bonfire.swf", "x": 1365, "y": 165, "bg": "Island.jpg",
             "battles": [{"name": "Island Party", "desc": "Hot, hot, hot!", "thumbnail": "Pirate.png",
                          "pets": [("TikiMask", 12), ("FireImp", 12), ("AirParrot", 12)], "dna": 15}]},
            {"id": 7, "name": "Frozen Sculpture", "desc": "An iceberg in the tropics. Something is wrong with the weather.",
             "asset": "Zone_2_Ice_Sculpture.swf", "x": 1360, "y": 405, "bg": "Iceberg.jpg",
             "battles": [{"name": "Ice Guardians", "desc": "They came with the cold.", "thumbnail": "SafariDude.png",
                          "pets": [("MiniYeti", 13), ("Penguin", 13), ("IceVulture", 13)], "dna": 10,
                          "enter": "z2n7_enter"}]},
            {"id": 8, "name": "Weather Machine", "desc": "Captain Blackfin's machine is stirring up the storm.",
             "asset": "Zone_2_Weather_Machine.swf", "x": 1080, "y": 300, "bg": "Ship.jpg", "complete_zone": True,
             "battles": [{"name": "Storm Crew", "desc": "The machine's guards.", "thumbnail": "Pirate.png",
                          "pets": [("ThunderBird", 14), ("Pelican", 14), ("Jellyfish", 14)], "dna": 10},
                         {"name": "Captain Blackfin", "desc": "The captain, working for the Legion.",
                          "thumbnail": "PirateCaptain.png", "pets": [("CapnSkelly", 15), ("ThunderBird", 15), ("PirateShark", 16)],
                          "dna": 10, "enter": "z2n8_enter", "victory": "z2n8_win"}]},
        ],
    },
]

HARD_LEVEL_BONUS = 10
DEFEAT_DIALOG = "hint_defeat"

# --------------------------------------------------------------------------------------
# Dialogs.  Frame fields: pos (left/right/center), image (dialog portrait file) and
# name, or player=<expression file> for the player's own portrait; bg is optional
# and stays until another bg is given.
# --------------------------------------------------------------------------------------

DIALOGS = {
    "start_game": [
        {"pos": "center", "bg": "Intro_House.jpg", "image": "Mom.png", "name": "Mom",
         "text": "^%name%^! Rise and shine! Your father and I have a surprise waiting for you downstairs."},
        {"pos": "left", "player": "Happy.png", "text": "A surprise? Is it... is it a curio?!"},
        {"pos": "right", "bg": "Intro_House_2.jpg", "image": "Dad.png", "name": "Dad",
         "text": "Not just any curio, @son/daughter@. This is ^Ducan^. He has been with our family for a long time, and now he is yours."},
        {"pos": "left", "player": "Surprised.png", "text": "He's amazing! Wait... why are there suitcases by the door?"},
        {"pos": "right", "image": "Mom.png", "name": "Mom",
         "text": "Sweetie, there is something we should have told you a long time ago. We weren't always just your parents..."},
        {"pos": "center", "bg": "Intro_Street.swf", "image": "LegionairesGroup.png", "name": "The Legion",
         "text": "This is the ^Galactic Legion^! Step out of the house with your hands where we can see them!"},
        {"pos": "center", "image": "ParentsHandcuff.png", "name": "Dad",
         "text": "%name%, listen to me! Take Ducan and go! Find the ^Hermit^ at the old dock. Don't trust the Legion!"},
        {"pos": "left", "bg": "Intro_InteriorWindow.swf", "player": "Scared.png",
         "text": "Mom! Dad! ...They're gone. They took them away."},
        {"pos": "right", "bg": "Intro_NewWorld.swf", "image": "Hermit.png", "name": "Hermit",
         "text": "Chin up, kid. Your parents are no criminals, whatever the Legion says. Cross the island and meet me at the dock, and train that Ducan along the way. You are going to need him."},
    ],
    "z1n1_enter": [
        {"pos": "right", "image": "SafariDude.png", "name": "Safari Sam",
         "text": "Whoa, easy there! Ever since the Legion landed, wild curios have been running all over the island."},
        {"pos": "right", "image": "SafariDude.png", "name": "Safari Sam",
         "text": "Tap one of your curio's skills to attack. Stronger skills cost ^mana^ and need a few turns to recharge. Let's see what that Ducan can do!"},
    ],
    "z1n1_win": [
        {"pos": "right", "image": "SafariDude.png", "name": "Safari Sam",
         "text": "Now that's a curio trainer! Wild curios you defeat sometimes want to ^join your team^. Keep battling and your collection will grow."},
    ],
    "z1n2_enter": [
        {"pos": "right", "image": "Jace.png", "name": "Jace",
         "text": "Hey, I know you! You're the kid whose parents got hauled off by the Legion. Nobody crosses my bridge without a battle!"},
        {"pos": "left", "player": "Angry.png", "text": "My parents didn't do anything wrong! Let's go, Ducan!"},
    ],
    "z1n2_win": [
        {"pos": "right", "image": "Jace.png", "name": "Jace",
         "text": "Okay, okay! You win. The bridge is all yours... and hey, sorry about your folks."},
    ],
    "z1n3_enter": [
        {"pos": "right", "image": "Lee.png", "name": "Lee",
         "text": "Shhh! The birds in the old treehouse are nesting, and their curios get grumpy when strangers climb up."},
        {"pos": "left", "player": "Confused.png", "text": "I just need to get to the other side of the island."},
        {"pos": "right", "image": "Lee.png", "name": "Lee", "text": "Then you'll have to get past them first. Good luck!"},
    ],
    "z1n4_enter": [
        {"pos": "right", "image": "Jeff.png", "name": "Jeff",
         "text": "This generator powers the whole island, and the Legion put me in charge of guarding it. Turn around!"},
        {"pos": "left", "player": "Normal.png", "text": "The Legion put you in charge? Then you know where they took my parents!"},
        {"pos": "right", "image": "Jeff.png", "name": "Jeff",
         "text": "Even if I did, I wouldn't tell a fugitive's kid. Curios, attack!"},
    ],
    "z1n5_enter": [
        {"pos": "right", "image": "Pirate.png", "name": "Pirate",
         "text": "Arr! This be where the treasure's buried, and it be OURS! Scram, landlubber!"},
        {"pos": "left", "player": "Happy.png", "text": "Pirates? On our island? Ducan, looks like we're digging for treasure today!"},
    ],
    "z1n6a_enter": [
        {"pos": "right", "image": "Pirate.png", "name": "Pirate",
         "text": "Captain! The @boy/girl@ from the beach is here, and @he/she@ brought that pesky Ducan!"},
    ],
    "z1n6b_enter": [
        {"pos": "right", "image": "PirateCaptain.png", "name": "Captain Blackfin",
         "text": "So you're the little runaway everyone is talking about. You want a boat? You'll have to take mine!"},
    ],
    "z1n6_win": [
        {"pos": "right", "image": "PirateCaptain.png", "name": "Captain Blackfin",
         "text": "Blast it! Fine, take the ship. But you haven't seen the last of me!"},
        {"pos": "right", "image": "Hermit.png", "name": "Hermit",
         "text": "Well fought, %name%. I saw the Legion's ship heading out across the ^Open Sea^. That pirate boat will get us there."},
        {"pos": "left", "player": "Happy.png", "text": "Hold on, Mom and Dad. We're coming!"},
    ],
    "z2n1_enter": [
        {"pos": "right", "image": "Hermit.png", "name": "Hermit",
         "text": "The Open Sea is full of [water] curios. [electric] skills hit them hard, but they will wash away any [fire] curio you bring."},
        {"pos": "right", "image": "Hermit.png", "name": "Hermit",
         "text": "Watch for the ^Strong^ and ^Weak^ markers during battle and choose your curios wisely."},
    ],
    "z2n4_enter": [
        {"pos": "right", "image": "Pirate.png", "name": "Pirate",
         "text": "Captain's orders: sink anyone who follows the Legion ship! ...Wait, what is that thing rising out of the water?!"},
        {"pos": "left", "player": "Scared.png", "text": "That's... a SEA MONSTER!"},
    ],
    "z2n5_enter": [
        {"pos": "left", "player": "Confused.png",
         "text": "Ugh... it's dark, it's slimy and it smells like old fish. We got swallowed by the sea monster!"},
        {"pos": "right", "image": "Hermit.png", "name": "Hermit",
         "text": "Don't panic! Beat the curios living in here and this big fella will spit us right back out."},
    ],
    "z2n7_enter": [
        {"pos": "right", "image": "SafariDude.png", "name": "Safari Sam",
         "text": "Brrr! An iceberg in the tropics? Something is messing with the weather out here, %name%."},
    ],
    "z2n8_enter": [
        {"pos": "right", "image": "PirateCaptain.png", "name": "Captain Blackfin",
         "text": "Surprised? My weather machine will drown every island from here to the horizon, and the Legion pays me handsomely for it!"},
        {"pos": "left", "player": "Angry.png", "text": "You're working for the Legion?! Ducan, let's shut this machine down!"},
    ],
    "z2n8_win": [
        {"pos": "right", "image": "LegionairesGroup.png", "name": "The Legion",
         "text": "Captain Blackfin, you failed. The prisoners have already been moved beyond the storm. Retreat!"},
        {"pos": "left", "player": "Sad.png", "text": "They're getting away again..."},
        {"pos": "right", "image": "Hermit.png", "name": "Hermit",
         "text": "Not for long. The sky is clearing and the way ahead is open. Rest up, %name%. The real journey starts now."},
    ],
    "hint_defeat": [
        {"pos": "right", "image": "Hermit.png", "name": "Hermit",
         "text": "Don't give up! Level up your curios, rank up their skills in the skill tree and try again."},
    ],
}

TIPS = [
    "Curios earn experience in every battle they win, and new skills unlock as they level up.",
    "[water] beats [fire], [fire] beats [air], [air] beats [earth], [earth] beats [electric] and [electric] beats [water].",
    "[light] and [dark] curios are strong against each other.",
    "Defending halves the damage your curio takes until its next turn.",
    "Energy refills over time. You spend it to battle in the zones.",
    "Defeated wild curios may offer to join your team after the battle.",
    "Curios evolve at levels 10 and 25 and get much stronger.",
    "Spend skill points in the skill tree to rank up your favorite skills.",
    "Spin the Prize Wheel every day for free rewards.",
    "Finish a zone to unlock its Hard difficulty.",
    "Curios with high luck land more critical hits.",
    "Healing skills grow with your curio's healing stat.",
]

# --------------------------------------------------------------------------------------
# Economy
# --------------------------------------------------------------------------------------

CURRENCIES = [
    # id, link, name, description, icon file (prize wheel icons shipped in the APK)
    (1, "gold", "Gold", "Coins used to evolve, rank up and buy curios.", "Gold.png"),
    (2, "credits", "Plasma", "Rare energy crystals used for premium items.", "Plasma.png"),
    (3, "bps", "Battle Points", "Earned by battling other players.", "ActivityPoints.png"),
    (4, "exp", "Experience", "Experience for your curios.", "Exp.png"),
    (5, "dust", "Stardust", "Left behind by exchanged curios. Used to rank up.", "RandomBoost.png"),
    (6, "energy", "Energy", "Spent to battle in the zones.", "Energy.png"),
    (7, "wheelspin", "Prize Wheel Spin", "One extra spin of the Prize Wheel.", "FreeSpin.png"),
    (8, "tokens", "Friend Tokens", "Used to play Plinko in the arcade.", "Token.png"),
    (9, "tickets", "PvP Tickets", "Used to battle in the arena.", "Tickets.png"),
    (10, "pvp", "Arena Coins", "Rewards from arena events.", "Credit.png"),
    (11, "event", "Event Coins", "Rewards from special events.", "RandomItem.png"),
    (12, "guild", "Club Coins", "Rewards from club battles.", "Token.png"),
    (13, "shipment", "Shipment Coins", "Rewards from shipments.", "RandomItem.png"),
]
CURRENCY_ID = {link: cid for cid, link, *_ in CURRENCIES}

SERVICES = [
    # id, type, name, description, value, gold, plasma, icon
    (1, "plinko", "Plinko Ball", "One extra Plinko ball.", 1, 0, 3, "Token.png"),
    (2, "teamslot", "Team Slot", "Unlocks one more curio team.", 1, 0, 50, "RandomCurio.png"),
    (3, "energy", "Energy Refill", "Refills your energy.", 20, 0, 10, "Energy.png"),
    (4, "tickets", "PvP Tickets", "Five arena tickets.", 5, 0, 10, "Tickets.png"),
    (5, "gold", "Gold Pouch", "A pouch with 5,000 gold.", 5000, 0, 20, "Gold.png"),
    (6, "skillreset", "Skill Reset", "Returns all skill points of a curio.", 1, 1000, 0, "ActivityPoints.png"),
    (7, "tokens", "Friend Tokens", "Ten Friend Tokens for the arcade.", 10, 0, 10, "Token.png"),
    (8, "upgradecooldownreset", "Upgrade Rush", "Skips the upgrade cooldown.", 1, 0, 5, "FreeSpin.png"),
    (9, "petmaxbonus", "Curio Storage", "Room for 10 more curios.", 10, 0, 25, "RandomItem.png"),
    (10, "name_change", "Name Change", "Choose a new player name.", 1, 0, 50, "Exp.png"),
]

GRAB_BAGS = [
    {"id": 1, "name": "Curio Capsule", "desc": "Contains a random curio.", "rarity": "rare", "icon": "RandomCurio.png",
     "cost_gold": 0, "cost_credits": 30, "roll": 1, "loot": "curios"},
    {"id": 2, "name": "Mystery Box", "desc": "A box full of surprises.", "rarity": "common", "icon": "RandomItem.png",
     "cost_gold": 2500, "cost_credits": 0, "roll": 1,
     # materials are only obtainable here: nothing else in the game grants or sells them yet
     "loot": [("currency", "gold", 1000, 30), ("currency", "energy", 10, 20), ("currency", "tokens", 5, 15),
              ("currency", "credits", 5, 10), ("grabbag", 1, 1, 5),
              ("material", 1, 2, 8), ("material", 2, 2, 7), ("material", 3, 1, 5)]},
]
CAPSULE_ODDS = {"common": 70, "rare": 25, "epic": 5}

DAILY_REWARDS = [
    [("currency", "gold", 500)],
    [("currency", "energy", 10)],
    [("currency", "gold", 1000)],
    [("currency", "tokens", 5)],
    [("currency", "credits", 10)],
    [("currency", "gold", 2500), ("currency", "tickets", 5)],
    [("grabbag", 1, 1)],
]

PRIZE_WHEEL = [
    # icon, reward, weight
    ("Gold.png", ("currency", "gold", 750), 20),
    ("Energy.png", ("currency", "energy", 5), 14),
    ("Exp.png", ("currency", "exp", 200), 12),
    ("Token.png", ("currency", "tokens", 3), 12),
    ("Plasma.png", ("currency", "credits", 5), 5),
    ("Tickets.png", ("currency", "tickets", 2), 10),
    ("RandomCurio.png", ("grabbag", 1, 1), 2),
    ("FreeSpin.png", ("currency", "wheelspin", 1), 6),
    ("ActivityPoints.png", ("currency", "bps", 50), 7),
    ("RandomItem.png", ("grabbag", 2, 1), 5),
    ("Credit.png", ("currency", "credits", 2), 4),
    ("RandomBoost.png", ("currency", "dust", 100), 3),
]

# The arcade board has exactly five slots: PlinkoWindow.showHit only lights up ids 0 to 4
# (rewardsA..rewardsE), so a sixth slot would be a prize the player could never see land.
# The middle slot is the one worth aiming at, the way these boards always read.
PLINKO = [
    # position, loot [(type, id, qty, perc)]
    (0, [("currency", "gold", 500, 80), ("currency", "tokens", 2, 20)]),
    (1, [("currency", "energy", 5, 60), ("currency", "gold", 1000, 40)]),
    (2, [("currency", "gold", 2000, 60), ("currency", "credits", 5, 30), ("grabbag", 1, 1, 10)]),
    (3, [("currency", "energy", 5, 60), ("currency", "gold", 1000, 40)]),
    (4, [("currency", "gold", 500, 80), ("currency", "tokens", 2, 20)]),
]

SUCCESS_RATES = [("Low", "FF4444", 0, 24), ("Medium", "FF9900", 25, 49), ("High", "FFFF00", 50, 74),
                 ("Very High", "66FF33", 75, 99), ("Guaranteed", "33FFFF", 100, 1000)]

# id, name, desc (# = amount), icon, objective, target, what the server counts, amounts, reward per rank
ACHIEVEMENTS = [
    (1, "Island Hopper", "Complete Home Island", "Zone_1.png", "complete", 1, "zone_complete:1", (1,), ("credits", 10)),
    (2, "Sea Legs", "Complete the Open Sea", "Zone_2.png", "complete", 2, "zone_complete:2", (1,), ("credits", 20)),
    (3, "Curio Tamer", "Win # zone battles", "DefeatNodes.png", "defeat", 0, "node_wins", (10, 50, 250, 1000), ("gold", 1000)),
    (4, "Hard Hitter", "Deal # damage", "DealDamage.png", "damage", -1, "damage", (10000, 100000, 1000000), ("gold", 1500)),
    (5, "Brawler", "Deal # [physical] damage", "DealPhysicalDamage.png", "damage", 0, "damage:physical", (5000, 50000, 500000), ("gold", 800)),
    (6, "Windbreaker", "Deal # [air] damage", "DealAirDamage.png", "damage", 1, "damage:air", (5000, 50000, 500000), ("gold", 800)),
    (7, "Landslide", "Deal # [earth] damage", "DealEarthDamage.png", "damage", 2, "damage:earth", (5000, 50000, 500000), ("gold", 800)),
    (8, "Shining Star", "Deal # [light] damage", "DealLightDamage.png", "damage", 3, "damage:light", (5000, 50000, 500000), ("gold", 800)),
    (9, "Night Terror", "Deal # [dark] damage", "DealDarkDamage.png", "damage", 4, "damage:dark", (5000, 50000, 500000), ("gold", 800)),
    (10, "Live Wire", "Deal # [electric] damage", "DealElectricDamage.png", "damage", 5, "damage:electric", (5000, 50000, 500000), ("gold", 800)),
    (11, "Tsunami", "Deal # [water] damage", "DealWaterDamage.png", "damage", 6, "damage:water", (5000, 50000, 500000), ("gold", 800)),
    (12, "Firestarter", "Deal # [fire] damage", "DealFireDamage.png", "damage", 7, "damage:fire", (5000, 50000, 500000), ("gold", 800)),
    (13, "Critical Thinker", "Land # critical hits", "DealCritical.png", "damage", -2, "crits", (25, 250, 2500), ("gold", 1000)),
    (14, "Field Medic", "Heal # health", "HealthHealed.png", "heal", 0, "healing", (5000, 50000, 500000), ("gold", 1000)),
    (15, "Gold Digger", "Collect # gold", "CollectGold.png", "collect", 1, "gold_earned", (10000, 100000, 1000000), ("credits", 5)),
    (16, "Scholar", "Earn # experience", "CollectExp.png", "collect", 4, "exp_earned", (1000, 10000, 100000), ("gold", 1000)),
    (17, "Plasma Collector", "Collect # plasma", "CollectPlasma.png", "collect", 2, "credits_earned", (50, 500, 5000), ("gold", 2500)),
    (18, "Common Ground", "Own # common curios", "CollectCommons.png", "collect", 0, "own:common", (5, 10, 20), ("gold", 1000)),
    (19, "Rare Finds", "Own # rare curios", "CollectRares.png", "collect", 0, "own:rare", (3, 6, 10), ("gold", 2000)),
    (20, "Epic Collection", "Own # epic curios", "CollectEpics.png", "collect", 0, "own:epic", (1, 3, 6), ("credits", 10)),
    (21, "Legend Keeper", "Own # legendary curios", "CollectLegendaries.png", "collect", 0, "own:legendary", (1,), ("credits", 25)),
    (22, "Unique Tastes", "Own # different curios", "UniqueCurios.png", "obtain", 1, "unique_species", (10, 25, 46), ("credits", 10)),
    (23, "Evolutionist", "Evolve # curios", "EvolveCurios.png", "evolve", 0, "evolves", (1, 10, 50), ("gold", 2000)),
    (24, "Rank Climber", "Rank up # curios", "RankUpCurios.png", "upgrade", 0, "rankups", (1, 10, 25), ("gold", 2000)),
    (25, "Max Power", "Raise # curios to level 40", "MaxLevel.png", "level", 40, "max_level", (1, 5, 20), ("credits", 10)),
    (26, "Plinko Pro", "Play Plinko # times", "PlayPlinko.png", "plinko", 0, "plinko", (10, 100, 500), ("tokens", 10)),
    (27, "Wheel of Fortune", "Spin the Prize Wheel # times", "PrizeWheel.png", "none", 0, "spins", (7, 30, 100), ("gold", 1000)),
    (28, "Job Well Done", "Complete # jobs", "CompleteJobs.png", "complete", 0, "jobs", (10, 100, 500), ("gold", 1500)),
    (29, "Fresh Start", "Reset a zone # times", "ResetZone.png", "reset", 0, "resets", (1, 10, 50), ("energy", 10)),
    (30, "Arena Rookie", "Win # PvP battles", "WinPvPBattles.png", "defeat", 1, "pvp_wins", (10, 100, 1000), ("tickets", 5)),
    (31, "Trade Master", "Exchange # curios", "ExchangedCurios.png", "exchange", 0, "exchanges", (5, 50, 250), ("dust", 200)),
    (32, "Big Spender", "Spend # plasma", "SpendPlasma.png", "none", 0, "credits_spent", (100, 1000), ("gold", 5000)),
    (33, "Journal Keeper", "Discover # curios", "JournalEntries.png", "obtain", 0, "journal", (10, 25, 46), ("gold", 2500)),
]

JOBS = [
    # id, name, desc, icon, objective, count, target, pet type, reward
    (1, "Warm-Up", "Win 3 zone battles.", "DefeatNodes.png", "defeat", 3, "node", None, ("gold", 300)),
    (2, "Battle Ready", "Fight 5 battles.", "WinCvEBattles.png", "fight", 5, "none", None, ("gold", 500)),
    (3, "Curio Trainer", "Level up a curio.", "MaxLevel.png", "level", 1, "pet", None, ("energy", 5)),
    (4, "Lucky Drop", "Play Plinko once.", "PlayPlinko.png", "plinko", 1, "self", None, ("tokens", 3)),
    (5, "Collector", "Get a new curio.", "UniqueCurios.png", "obtain", 1, "pet", None, ("credits", 5)),
    (6, "Power Up", "Rank up or evolve a curio.", "RankUpCurios.png", "upgrade", 1, "pet", None, ("gold", 1000)),
    (7, "Arena Challenger", "Fight 3 PvP battles.", "WinPvPBattles.png", "fight", 3, "pvp", None, ("tickets", 3)),
    (8, "Fire Fighter", "Defeat 5 fire curios.", "DealFireDamage.png", "defeat", 5, "pet", "fire", ("gold", 800)),
    (9, "Wave Breaker", "Defeat 5 water curios.", "DealWaterDamage.png", "defeat", 5, "pet", "water", ("gold", 800)),
    (10, "Light Bringer", "Defeat 5 dark curios.", "DealDarkDamage.png", "defeat", 5, "pet", "dark", ("gold", 800)),
]

SHOP_TABS = [
    {"name": "Curios", "items": "curios"},
    {"name": "Items", "items": [("grabbag", 1, "A random curio!"), ("grabbag", 2, "Gold, energy and more."),
                                ("service", 3, "Get back into battle."), ("service", 7, "Play more Plinko."),
                                ("service", 4, "Battle in the arena."), ("service", 5, "Instant gold.")]},
    {"name": "Services", "items": [("service", 2, "Build another team."), ("service", 9, "Keep more curios."),
                                   ("service", 6, "Try a new build."), ("service", 10, "A fresh start.")]},
    # A tab is also what authorises a purchase: MerchantDALC refuses anything no tab lists.
    {"name": "Enhancements", "items": [("consumable", 1, "More health, for good."),
                                       ("consumable", 2, "More damage, for good."),
                                       ("consumable", 3, "More healing, for good."),
                                       ("consumable", 4, "Crit more often."),
                                       ("consumable", 5, "Cast the heavy skills sooner."),
                                       ("consumable", 6, "A lot more health."),
                                       ("consumable", 7, "A lot more damage."),
                                       ("consumable", 8, "A lot more healing."),
                                       ("consumable", 9, "Health and damage at once."),
                                       ("consumable", 10, "Every stat at once.")]},
    # Only the first tier is sold: Ruby/Amber/Sapphire Chip, one per socket colour.  Everything
    # above comes from PetDALC.UPGRADE_ENCHANT, so the shop does not short-circuit the progression.
    {"name": "Boosts", "items": [("enchant", 1, "Red socket: more damage."),
                                 ("enchant", 4, "Yellow socket: more luck."),
                                 ("enchant", 7, "Blue socket: more health.")]},
]

VARIABLES = {
    "energyCooldown": 180000, "energyMax": 30,
    "tokenCooldown": 1800000, "tokenMax": 10,
    "ticketCooldown": 3600000, "ticketMax": 5,
    "fatigueCooldown": 60000, "fatigueMax": 100,
    "skillSlots": 4, "friendsMax": 50, "petDuplicateMax": 99, "petTeamSize": 3,
    "petPrestigeGain": 0, "petLimit": 100, "petBonusLimit": 400,
    "consumableGoldBase": 100, "consumableGoldPerLevel": 10,
    "teamsMin": 1, "teamsMax": 5,
    "pvpEventBattleTickets": 1, "pvpEventRepickTickets": 1, "gvgEventBattleTokens": 1, "gvgEventRepickTokens": 1,
    "upgradePlasmaResetCost": 5,
    "plinkoCostItemType": 3, "plinkoCostItemID": 8, "plinkoCostItemQty": 5,
    # loadingTag is appended to every asset URL by the client, so it must be URL-safe (empty is fine)
    "characterLoadLocal": "true", "loadingTag": "",
    "tapjoyEnabled": "false", "facebookEnabled": "false", "leaderboardEnabled": "false",
    "guildInitialChars": 3,
    "livePvPEnabled": "false", "livePvPInfo": "", "livePvPBG": "Colosseum.jpg", "livePvPTurnSeconds": 30,
    "chatEnabled": "false", "chatAgeConfirm": "", "chatMuteSeconds": "300,3600,86400",
    "chatMuteReasons": "Spam,Language,Harassment", "chatChannels": "Global", "chatTermsOfService": "",
    "paymentCheck": "false", "showSeasonDecaration": "false", "seasonDecarationAsset": "",
    "limitedOfferRotation": 0, "maxJobsPerDay": 5, "notificationRetentionSeconds": "86400,259200,604800",
}

# Server-side balance (read by the server from the generated XML, ignored by the client).
# The client calls these "Enhancements" (ItemRef.ITEM_TYPE_NAMES[ITEM_TYPE_CONSUMABLE]), so the
# authored text uses that word too.  Using one permanently raises a stat of a single curio; a curio
# whose element is listed in bonus_types gets the second (larger) number instead of the first.
# use_gold is the gold the client charges on top of owning the item.
# No consumable art shipped in the APK, so the icons alias to prize wheel icons that did.
CONSUMABLES = [
    {"id": 1, "name": "Vigor Tonic", "desc": "Permanently raises a curio's ^health^. Works best on [earth] and [physical] curios.",
     "rarity": "common", "icon": "RandomBoost.png", "cost_gold": 350, "cost_credits": 0, "sell_gold": 35,
     "use_gold": 100, "bonus_types": ("earth", "physical"), "stats": {"health": (25, 40)}},
    {"id": 2, "name": "Power Draught", "desc": "Permanently raises a curio's ^damage^. Works best on [fire] and [dark] curios.",
     "rarity": "common", "icon": "ActivityPoints.png", "cost_gold": 450, "cost_credits": 0, "sell_gold": 45,
     "use_gold": 100, "bonus_types": ("fire", "dark"), "stats": {"damage": (5, 8)}},
    {"id": 3, "name": "Mender's Salve", "desc": "Permanently raises a curio's ^healing^. Works best on [light] and [water] curios.",
     "rarity": "common", "icon": "Exp.png", "cost_gold": 420, "cost_credits": 0, "sell_gold": 42,
     "use_gold": 100, "bonus_types": ("light", "water"), "stats": {"healing": (8, 12)}},
    {"id": 4, "name": "Lucky Coin", "desc": "Permanently raises a curio's ^luck^, which decides how often it lands a critical hit.",
     "rarity": "rare", "icon": "Credit.png", "cost_gold": 900, "cost_credits": 0, "sell_gold": 90,
     "use_gold": 150, "bonus_types": (), "stats": {"luck": (3, 3)}},
    {"id": 5, "name": "Focus Crystal", "desc": "Permanently raises a curio's ^mana^, so it can cast its heavier skills sooner.",
     "rarity": "rare", "icon": "Plasma.png", "cost_gold": 0, "cost_credits": 30, "sell_gold": 300,
     "use_gold": 250, "bonus_types": ("air", "electric"), "stats": {"mana": (1, 2)}},
    {"id": 6, "name": "Greater Vigor Tonic", "desc": "A far stronger ^health^ tonic. Works best on [earth] and [physical] curios.",
     "rarity": "epic", "icon": "RandomBoost.png", "cost_gold": 0, "cost_credits": 45, "sell_gold": 450,
     "use_gold": 400, "bonus_types": ("earth", "physical"), "stats": {"health": (60, 90)}},
    {"id": 7, "name": "Greater Power Draught", "desc": "A far stronger ^damage^ draught. Works best on [fire] and [dark] curios.",
     "rarity": "epic", "icon": "ActivityPoints.png", "cost_gold": 0, "cost_credits": 50, "sell_gold": 500,
     "use_gold": 400, "bonus_types": ("fire", "dark"), "stats": {"damage": (12, 18)}},
    {"id": 8, "name": "Greater Mender's Salve", "desc": "A far stronger ^healing^ salve. Works best on [light] and [water] curios.",
     "rarity": "epic", "icon": "Exp.png", "cost_gold": 0, "cost_credits": 45, "sell_gold": 450,
     "use_gold": 400, "bonus_types": ("light", "water"), "stats": {"healing": (18, 26)}},
    {"id": 9, "name": "Hero's Elixir", "desc": "Raises ^health^ and ^damage^ at once. Any curio can drink it.",
     "rarity": "legendary", "icon": "RandomItem.png", "cost_gold": 0, "cost_credits": 120, "sell_gold": 1200,
     "use_gold": 1000, "bonus_types": (), "stats": {"health": (80, 80), "damage": (14, 14)}},
    {"id": 10, "name": "Prismatic Essence", "desc": "Raises every stat of one curio. The rarest enhancement there is.",
     "rarity": "mythic", "icon": "RandomCurio.png", "cost_gold": 0, "cost_credits": 300, "sell_gold": 3000,
     "use_gold": 2500, "bonus_types": (), "stats": {"health": (100, 100), "damage": (18, 18),
                                                    "healing": (20, 20), "luck": (4, 4), "mana": (1, 1)}},
]

# Materials are plain held items: the client keeps them in the bag and spends them elsewhere.
# Ids 48, 49 and 50 are NOT free - MaterialBook hard-codes them as the core fragments
# (EPIC_CORE_FRAGMENT / LEGENDARY_CORE_FRAGMENT / MYTHIC_CORE_FRAGMENT), so they keep those ids.
MATERIALS = [
    {"id": 1, "name": "Scrap Metal", "desc": "Bent plating from a crashed shuttle. Useful to a patient builder.",
     "rarity": "common", "icon": "RandomItem.png", "cost_gold": 0, "cost_credits": 0, "sell_gold": 25},
    {"id": 2, "name": "Glass Shard", "desc": "A sliver of cockpit glass, still faintly warm.",
     "rarity": "common", "icon": "RandomItem.png", "cost_gold": 0, "cost_credits": 0, "sell_gold": 25},
    {"id": 3, "name": "Coral Bead", "desc": "Washed up on the beach at Home Island.",
     "rarity": "common", "icon": "RandomBoost.png", "cost_gold": 0, "cost_credits": 0, "sell_gold": 40},
    {"id": 4, "name": "Beacon Filament", "desc": "The glowing thread from inside a distress beacon.",
     "rarity": "rare", "icon": "Energy.png", "cost_gold": 0, "cost_credits": 0, "sell_gold": 150},
    {"id": 5, "name": "Starfall Ore", "desc": "Ore that only forms where a meteor has struck.",
     "rarity": "epic", "icon": "Gold.png", "cost_gold": 0, "cost_credits": 0, "sell_gold": 400},
    {"id": 48, "name": "Epic Core Fragment", "desc": "Part of an epic curio core. Collect them to rebuild the core.",
     "rarity": "epic", "icon": "RandomCurio.png", "cost_gold": 0, "cost_credits": 0, "sell_gold": 500},
    {"id": 49, "name": "Legendary Core Fragment", "desc": "Part of a legendary curio core.",
     "rarity": "legendary", "icon": "RandomCurio.png", "cost_gold": 0, "cost_credits": 0, "sell_gold": 1500},
    {"id": 50, "name": "Mythic Core Fragment", "desc": "Part of a mythic curio core. Vanishingly rare.",
     "rarity": "mythic", "icon": "RandomCurio.png", "cost_gold": 0, "cost_credits": 0, "sell_gold": 5000},
]

# What a new player starts with, written into VariableBook as <newPlayerGold> and friends.
# MUST mirror NEW_PLAYER in server/game/player.py, which is what actually creates the character:
# this copy said 1000 while the server handed out 500, and the two disagreed in the player's face.
# (The server's rating and teams_max stay out of here; they are not player-facing numbers.)
# Alternate looks: a skin lends one species the art of another, which is free content because all
# 46 surviving curios ship base/_E1/_E2 art in the APK.  Ids MUST be positive: PetSkinWindow uses
# negative ids (0, -1, -2) for the curio's own prestige looks and positive ones for SkinBook.
# The window lists every skin authored for the species - there is no ownership check in the client,
# so authoring one is what makes it selectable.
# id, pet_id (species id), art (the asset borrowed), name, desc, rarity
SKINS = [
    {"id": 1, "pet_id": 15, "art": "Penguin", "rarity": "rare", "name": "Tuxedo Ducan",
     "desc": "Ducan dressed for the cold, borrowed from the island's penguins."},
    {"id": 2, "pet_id": 12, "art": "Turnip", "rarity": "common", "name": "Rooted Cocon",
     "desc": "A Cocon that stayed in the ground a little too long."},
    {"id": 3, "pet_id": 19, "art": "FireCrab", "rarity": "common", "name": "Emberclaw Impkin",
     "desc": "An Impkin that traded its horns for a pair of burning claws."},
    {"id": 4, "pet_id": 41, "art": "Bat", "rarity": "common", "name": "Nightwing Shado",
     "desc": "The shadow took wing and never came back down."},
    {"id": 5, "pet_id": 20, "art": "PlantToad", "rarity": "common", "name": "Toadbloom Rosie",
     "desc": "Rosie's petals closed around something that croaks."},
    {"id": 6, "pet_id": 2, "art": "Pelican", "rarity": "rare", "name": "Gale Pigale",
     "desc": "Pigale caught a sea breeze and came back with a beak."},
]

# Handed out once, the first time the menu opens.  MenuScreen.checkWelcomePack keeps asking on
# every menu open until the player OWNS the pack item itself, so the server grants that too as
# the "already claimed" marker - see MerchantDALC action 8 in server/game/dalcs/merchant.py.
WELCOME_PACK = {
    "id": 1, "name": "Welcome Pack", "rarity": "epic", "icon": "RandomItem.png",
    "desc": "A hand from the islanders to get you started.",
    "items": [("currency", "gold", 1000), ("currency", "credits", 25),
              ("currency", "energy", 20), ("grabbag", 1, 1)],
}

# Crafting.  CraftRef.isCraftable() is decided entirely on the client from the player's own bag,
# so every ingredient here must be something the game actually hands out - these all come from the
# Mystery Box (materials 1-3) or from earlier recipes.  Recipes that need unobtainable items would
# simply sit greyed out forever.
# Enchants ("Boosts" in the client's own words).  A curio has three coloured slots - red=1,
# yellow=2, blue=3 - and an enchant declares which ones it fits through a comma-separated
# `slots` string.  The stats are flat adds on top of everything else.
# upgradeID points BACKWARDS: EnchantBook.getUpgradeEnchant looks for the enchant whose
# upgradeID equals the current one's id, so tier 2 carries tier 1's id, and tier 1 carries none.
# No enchant art survived in the APK, so the icons alias to prize wheel icons.
ENCHANT_SHOP_GOLD = 800   # only tier 1 is sold; the higher tiers come from UPGRADE_ENCHANT
ENCHANTS = [
    {"id": 1, "name": "Ruby Chip", "slots": "red", "rarity": "common", "icon": "ActivityPoints.png",
     "desc": "A chip of fire-glass. Raises ^damage^.",
     "stats": {"damage": 8}, "destroy_gold": 50, "upgrade_gold": 600, "upgrade_id": None},
    {"id": 2, "name": "Ruby Shard", "slots": "red", "rarity": "rare", "icon": "ActivityPoints.png",
     "desc": "A shard of fire-glass. Raises ^damage^ a lot.",
     "stats": {"damage": 18}, "destroy_gold": 150, "upgrade_gold": 2000, "upgrade_id": 1},
    {"id": 3, "name": "Ruby Core", "slots": "red", "rarity": "epic", "icon": "ActivityPoints.png",
     "desc": "The heart of a fire-glass vein. Raises ^damage^ enormously.",
     "stats": {"damage": 32}, "destroy_gold": 400, "upgrade_gold": 0, "upgrade_id": 2},

    {"id": 4, "name": "Amber Chip", "slots": "yellow", "rarity": "common", "icon": "Credit.png",
     "desc": "Warm amber. Raises ^luck^.",
     "stats": {"luck": 4}, "destroy_gold": 50, "upgrade_gold": 600, "upgrade_id": None},
    {"id": 5, "name": "Amber Shard", "slots": "yellow", "rarity": "rare", "icon": "Credit.png",
     "desc": "Clear amber. Raises ^luck^ a lot.",
     "stats": {"luck": 9}, "destroy_gold": 150, "upgrade_gold": 2000, "upgrade_id": 4},
    {"id": 6, "name": "Amber Core", "slots": "yellow", "rarity": "epic", "icon": "Credit.png",
     "desc": "Amber with something alive inside. Raises ^luck^ and ^mana^.",
     "stats": {"luck": 16, "mana": 1}, "destroy_gold": 400, "upgrade_gold": 0, "upgrade_id": 5},

    {"id": 7, "name": "Sapphire Chip", "slots": "blue", "rarity": "common", "icon": "RandomBoost.png",
     "desc": "Cold blue stone. Raises ^health^ and ^healing^.",
     "stats": {"health": 60, "healing": 6}, "destroy_gold": 50, "upgrade_gold": 600, "upgrade_id": None},
    {"id": 8, "name": "Sapphire Shard", "slots": "blue", "rarity": "rare", "icon": "RandomBoost.png",
     "desc": "Deep blue stone. Raises ^health^ and ^healing^ a lot.",
     "stats": {"health": 130, "healing": 14}, "destroy_gold": 150, "upgrade_gold": 2000, "upgrade_id": 7},
    {"id": 9, "name": "Sapphire Core", "slots": "blue", "rarity": "epic", "icon": "RandomBoost.png",
     "desc": "A frozen spring in stone. Raises ^health^ and ^healing^ enormously.",
     "stats": {"health": 240, "healing": 26}, "destroy_gold": 400, "upgrade_gold": 0, "upgrade_id": 8},
]

# Battle loot.  ZoneNodeBattleRef has no loot field and ZoneBook never parses one, so the drops
# are the server's to decide: they reach the client as the ITEM_LIST of RESULTS, which BattlePlugin
# pours into an ItemSelectWindow("Loot").  Materials exist for crafting, and the Mystery Box alone
# (8/7/5% at 2500 gold a box) made a single recipe cost about 165,000 gold - crafting was dead.
# (material id, percent chance per won battle), by the average level of the fight.
BATTLE_LOOT = [
    (0,  [(1, 30), (2, 25)]),                       # first nodes: scrap and glass
    (5,  [(1, 25), (2, 25), (3, 20)]),              # coral joins in
    (10, [(2, 20), (3, 25), (4, 12)]),              # beacon filament starts appearing
    (20, [(3, 20), (4, 18), (5, 8)]),               # starfall ore at the deep end
]

CRAFT_TABS = [(0, "Enhancements"), (1, "Cores")]
CRAFTS = [
    {"id": 1, "tab": 0, "result": ("consumable", 1, 1),
     "items": [("material", 1, 3), ("material", 2, 2)]},
    {"id": 2, "tab": 0, "result": ("consumable", 2, 1),
     "items": [("material", 1, 3), ("material", 3, 2)]},
    {"id": 3, "tab": 0, "result": ("consumable", 3, 1),
     "items": [("material", 3, 3), ("material", 2, 2)]},
    {"id": 4, "tab": 0, "result": ("consumable", 5, 1),
     "items": [("material", 4, 2), ("material", 2, 3)]},
    {"id": 5, "tab": 1, "result": ("material", 48, 1),
     "items": [("material", 4, 5)]},
    {"id": 6, "tab": 1, "result": ("material", 49, 1),
     "items": [("material", 48, 3), ("material", 5, 2)]},
    {"id": 7, "tab": 1, "result": ("material", 50, 1),
     "items": [("material", 49, 3), ("material", 5, 5)]},
]

NEW_PLAYER = {"gold": 500, "credits": 25, "energy": 20, "tokens": 5, "tickets": 5}
