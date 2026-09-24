"""JobDALC (DALC_ID 9): the daily jobs and their loot."""
import logging

from ...es5.esobject import EsObject
from ..dalc import Dalc, action
from ..keys import K
from .. import progress, rewards

log = logging.getLogger("jobdalc")

UPDATE_PROGRESS = 1
GET_LOOT = 2
LOAD_START_JOBS = 3

# model.utility.ErrorCode
JOB_INVALID = 37
JOB_INCOMPLETE = 38
JOB_LOOTED = 39


class JobDalc(Dalc):
    dalc_id = 9
    name = "JobDALC"

    @action(GET_LOOT)
    async def get_loot(self, session, request):
        player = session.data.get("player")
        if player is None:
            return EsObject().set_integer(K.ACTION_ERROR, JOB_INVALID)
        job_id = int(request.get(K.JOB_ID, 0))
        job = next((j for j in player["jobs_active"] if j["id"] == job_id), None)
        ref = self.game.data.jobs.get(job_id)
        if job is None or ref is None:
            return EsObject().set_integer(K.ACTION_ERROR, JOB_INVALID)
        if job["looted"]:
            return EsObject().set_integer(K.ACTION_ERROR, JOB_LOOTED)
        if job["progress"] < ref.count:
            return EsObject().set_integer(K.ACTION_ERROR, JOB_INCOMPLETE)
        # JobData.isComplete olha SO para progress >= count e ignora _isLooted, e Jobs nao filtra
        # nada do que o servidor manda.  Um trabalho recolhido que continue em CHARACTER_JOBS_ACTIVE
        # faz MenuScreen.checkTutorial() reencontra-lo, pedir o loot de novo, receber JOB_LOOTED e
        # chamar checkTutorial() outra vez - recursao infinita que trava a tela no LOADING.
        job["looted"] = True
        player["jobs_active"] = [j for j in player["jobs_active"] if j["id"] != job_id]
        if job_id not in player["jobs_complete"]:
            player["jobs_complete"].append(job_id)
        items = rewards.give_all(player, self.game.data, ref.rewards)
        progress.bump(player, "jobs", 1)
        log.info("[%d] trabalho '%s' recolhido", session.id, ref.name)
        # looting a job is itself tracked by an achievement, so let the game push what moved
        self.game.push_progress(session, player)
        self.game.players.save(player)
        reply = self.job_lists(player)
        reply.set_esobject_array(K.ITEM_LIST, items)
        return reply.set_integer(K.CHARACTER_GOLD, player["gold"])

    # ------------------------------------------------------------- server pushes
    def push_start(self, session, player):
        """MenuScreen.onJobStart replaces the whole job panel with what this carries."""
        self.send(session, LOAD_START_JOBS, self.job_lists(player))

    def push_progress(self, session, jobs):
        if not jobs:
            return
        eso = EsObject()
        eso.set_esobject_array(K.JOBS_UPDATED, [self.job_esobject(job) for job in jobs])
        self.send(session, UPDATE_PROGRESS, eso)

    # ------------------------------------------------------------------ helpers
    def job_lists(self, player):
        eso = EsObject()
        eso.set_esobject_array(K.CHARACTER_JOBS_ACTIVE,
                               [self.job_esobject(job) for job in player["jobs_active"] if not job["looted"]])
        return eso.set_integer_array(K.CHARACTER_JOBS_COMPLETE, player["jobs_complete"])

    @staticmethod
    def job_esobject(job):
        return (EsObject().set_integer(K.JOB_ID, job["id"]).set_integer(K.JOB_PROGRESS, job["progress"])
                .set_boolean(K.JOB_ISLOOTED, job["looted"]))
