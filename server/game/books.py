"""Game data "Books" (PetBook.xml, SkillBook.xml, ...), sent zlib-compressed in the login response."""
import logging
import zlib
from pathlib import Path

from ..es5.esobject import EsObject
from .keys import K

log = logging.getLogger("books")

# every XML the client reads through XMLBook.getXML() (Project.initBooks, XMLBook.doClientRefresh)
CLIENT_BOOKS = (
    "AchievementBook.xml", "ConsumableBook.xml", "CraftBook.xml", "CurrencyBook.xml", "DailyBook.xml",
    "DialogBook.xml", "EnchantBook.xml", "FilterBook.xml", "FvFEventBook.xml", "GrabBagBook.xml",
    "GuildBook.xml", "GvEEventBook.xml", "GvGEventBook.xml", "InAppBook.xml", "JobBook.xml",
    "LimitedOfferBook.xml", "MarketingBook.xml", "MaterialBook.xml", "NewsBook.xml", "PetBook.xml",
    "PetCollectionBook.xml", "PetFusionBook.xml", "PetRankBook.xml", "PetTypeBook.xml", "PlinkoBook.xml",
    "PrizeWheelBook.xml", "PvEEventBook.xml", "PvPEventBook.xml", "RarityBook.xml", "RarityOverrideBook.xml",
    "ReferBook.xml", "ServiceBook.xml", "ShopBook.xml", "SkillBook.xml", "SkinBook.xml", "SocialBook.xml",
    "SoundBook.xml", "SuccessBook.xml", "TimedModifierBook.xml", "TipBook.xml", "VariableBook.xml",
    "VideoOfferBook.xml", "WelcomePackBook.xml", "ZoneBook.xml",
)


class BookStore:
    def __init__(self, books_dir):
        self.books_dir = Path(books_dir)
        self._entries = None

    def reload(self):
        self._entries = None

    def path(self, name):
        return self.books_dir / name

    def esobjects(self):
        if self._entries is None:
            files = {p.name: p for p in sorted(self.books_dir.glob("*.xml"))}
            missing = [name for name in CLIENT_BOOKS if name not in files]
            if missing:
                log.warning("%d Books ausentes (o cliente vai falhar ao iniciar): %s", len(missing), ", ".join(missing))
            self._entries = [
                EsObject().set_string(K.XML_NAME, name).set_byte_array(K.XML_DATA, zlib.compress(path.read_bytes(), 9))
                for name, path in files.items()
            ]
            log.info("%d Books carregados de %s", len(self._entries), self.books_dir)
        return self._entries
