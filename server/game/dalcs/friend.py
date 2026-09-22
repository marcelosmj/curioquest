"""FriendDALC (DALC_ID 6): what the menu asks for when there is nobody to be friends with.

An offline server has no other players, so the friend screens have nothing to show.  Two things
still reach us and both deserve a straight answer instead of a warning in the log:

- CHECK_FRIENDS_ACHIEVEMENT, which MenuSlider fires on every menu open, has no case at all in the
  client's FriendDALC.parse, so the honest answer is silence.
- LOAD_GIFT_COUNT is consumed: MenuFriendPanel.updateGiftCount greys the "get gifts" button out
  when the count is zero, which is exactly the state we want it in.
"""
import logging

from ...es5.esobject import EsObject
from ..dalc import Dalc, action
from ..keys import K

log = logging.getLogger("frienddalc")

CHECK_FRIENDS_ACHIEVEMENT = 16
LOAD_GIFT_COUNT = 20


class FriendDalc(Dalc):
    dalc_id = 6
    name = "FriendDALC"

    @action(CHECK_FRIENDS_ACHIEVEMENT)
    async def check_friends_achievement(self, session, request):
        return None

    @action(LOAD_GIFT_COUNT)
    async def load_gift_count(self, session, request):
        return EsObject().set_integer(K.FRIEND_GIFT_COUNT, 0)
