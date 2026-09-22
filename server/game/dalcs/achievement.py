"""AchievementDALC (DALC_ID 13): progress and the rewards for each rank.

Nothing in the client ever asks for this: the achievement screen only listens, so both actions
are pushed by the server when something the player did moved an achievement.
"""
import logging

from ...es5.esobject import EsObject
from ..dalc import Dalc
from ..keys import K

log = logging.getLogger("achievedalc")

GET_REWARD = 1
UPDATE_ACHIEVEMENT = 2


class AchievementDalc(Dalc):
    dalc_id = 13
    name = "AchievementDALC"

    def push_updates(self, session, entries):
        if not entries:
            return
        eso = EsObject()
        eso.set_esobject_array(K.ACHIEVEMENTS_UPDATED, [self.esobject(entry) for entry in entries])
        self.send(session, UPDATE_ACHIEVEMENT, eso)

    def push_reward(self, session, player, entry, items):
        """MenuScreen.onAchieveReward opens the congratulations window with exactly this."""
        eso = self.esobject(entry)
        eso.set_esobject_array(K.ITEM_LIST, items)
        self.send(session, GET_REWARD, eso.set_integer(K.CHARACTER_GOLD, player["gold"]))

    @staticmethod
    def esobject(entry):
        return (EsObject().set_integer(K.ACHIEVEMENT_ID, entry["id"])
                .set_integer(K.ACHIEVEMENT_PROGRESS, entry["progress"])
                .set_integer(K.ACHIEVEMENT_RANK, entry["rank"]))
