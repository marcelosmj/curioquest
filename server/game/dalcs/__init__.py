"""Server side of the client's DALCs (see server/game/dalc.py)."""
from .achievement import AchievementDalc
from .character import CharacterDalc
from .friend import FriendDalc
from .game import GameDalc
from .job import JobDalc
from .merchant import MerchantDalc
from .pet import PetDalc

ALL_DALCS = (CharacterDalc, GameDalc, MerchantDalc, FriendDalc, PetDalc, JobDalc, AchievementDalc)
