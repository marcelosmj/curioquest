"""Daily jobs and achievements: the one place that turns what a player did into progress.

The client asks for almost none of this.  JobDALC.LOAD_START_JOBS, JobDALC.UPDATE_PROGRESS and
both AchievementDALC actions are pushed by the server; the only request is JobDALC.GET_LOOT,
sent when the player taps a job that is already finished.
"""
import logging
import random
import time

from . import rewards

log = logging.getLogger("progress")

DAY_SECONDS = 24 * 3600
RARITIES = ("common", "rare", "epic", "legendary", "mythic")

# Only objectives the server can actually watch today may be drawn, or a player can wake up to a
# whole day of jobs nothing can finish (arena, evolving and the arcade are not in yet).
TRACKABLE = ("defeat", "fight", "level", "upgrade", "plinko")


def counters(player):
    return player.setdefault("counters", {})


def bump(player, track, amount=1):
    """Raise a running count (damage dealt, battles won, gold earned...)."""
    if amount > 0:
        counters(player)[track] = counters(player).get(track, 0) + int(amount)


def snapshot(player, data):
    """Tracks that are a reading of the save instead of a running count."""
    owned = [data.species[pet["species"]] for pet in player["pets"] if pet["species"] in data.species]
    seen = {species.id for species in owned} | {int(key) for key in player.get("dna", {})}
    values = {"own:" + rarity: sum(1 for s in owned if s.rarity == rarity) for rarity in RARITIES}
    values["unique_species"] = len({species.id for species in owned})
    values["journal"] = len(seen)
    values["max_level"] = sum(1 for pet in player["pets"] if pet["species"] in data.species
                              and pet["level"] >= data.max_level(data.species[pet["species"]], pet["prestige"]))
    for zone in player["zones"]:
        if zone["difficulty"] == 0:
            values["zone_complete:%d" % zone["zone_id"]] = zone.get("completes", 0)
    return values


def value(player, data, track):
    return snapshot(player, data).get(track, counters(player).get(track, 0))


# ---------------------------------------------------------------------- jobs
def ensure_daily_jobs(player, data, now=None):
    """A fresh set of jobs every day, the same set all day for a given player."""
    day = int((now or time.time()) // DAY_SECONDS)
    if player.get("jobs_day") == day and player["jobs_active"]:
        return False
    wanted = max(1, data.var("maxJobsPerDay", 5))
    pool = sorted(job_id for job_id, ref in data.jobs.items() if ref.objective in TRACKABLE)
    if not pool:
        pool = sorted(data.jobs)
    if not pool:
        return False
    draw = random.Random("%s-%s" % (player["char_id"], day))
    player["jobs_day"] = day
    player["jobs_active"] = [{"id": job_id, "progress": 0, "looted": False}
                             for job_id in draw.sample(pool, min(wanted, len(pool)))]
    player["jobs_complete"] = []
    # the day also brings the free spin of the prize wheel
    player["num_free_spins"] = max(player.get("num_free_spins", 0), 1)
    return True


def advance_jobs(player, data, objective, amount=1, target="", pet_type=""):
    """Move every active job that is waiting for this kind of deed; returns the ones that moved."""
    moved = []
    for job in player["jobs_active"]:
        ref = data.jobs.get(job["id"])
        if ref is None or job["looted"] or ref.objective != objective:
            continue
        if ref.target and target and ref.target != target:
            continue
        if ref.pet_type and ref.pet_type != pet_type:
            continue
        if job["progress"] >= ref.count:
            continue
        job["progress"] = min(ref.count, job["progress"] + amount)
        moved.append(job)
    return moved


# -------------------------------------------------------------- achievements
def entry_for(player, achievement_id):
    entries = player.setdefault("achievements", [])
    entry = next((e for e in entries if e["id"] == achievement_id), None)
    if entry is None:
        entry = {"id": achievement_id, "progress": 0, "rank": 0}
        entries.append(entry)
    return entry


def check_achievements(player, data):
    """Bring every achievement up to date and pay for the ranks just reached.

    The client's rank is how many ranks were already awarded (Achievements.currAchievements hides
    the ones at getMaxRank), so each rank is paid once and the counter only ever climbs.
    """
    values = snapshot(player, data)
    running = counters(player)
    updated, awarded = [], []
    for ref in data.achievements.values():
        current = values.get(ref.track, running.get(ref.track, 0))
        entry = entry_for(player, ref.id)
        if current == entry["progress"]:
            continue
        entry["progress"] = current
        updated.append(entry)
        while entry["rank"] < len(ref.ranks) and current >= ref.ranks[entry["rank"]].needed:
            rank = ref.ranks[entry["rank"]]
            entry["rank"] += 1
            items = rewards.give_all(player, data, rank.rewards)
            log.info("conquista '%s' rank %d concluida", ref.name, entry["rank"])
            awarded.append((ref, entry, items))
    return updated, awarded
