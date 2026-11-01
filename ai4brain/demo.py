"""Builds a clearly-labelled sample profile by running a simulated learner through the real app code."""

import random
from datetime import timedelta

from . import collab, engine, planner, sim, twin
from .dimensions import DIMENSION_KEYS
from .storage import iso, utcnow

START_THETAS = {
    "attention": 0.1, "working_memory": -0.5, "processing_speed": 0.5, "logical_reasoning": 0.6,
    "cognitive_flexibility": -0.6, "verbal_reasoning": 0.9, "spatial_reasoning": -0.8,
    "decision_making": 0.0, "creative_thinking": 0.2, "metacognition": 0.3,
}
DAYS_BACK = 42
GROWTH_PER_PRACTICE = 0.05


def _run_session(db, profile_id, user, dimension, mode, when, rng, mood=None):
    start = engine.start_session(db, profile_id, dimension, mode, mood=mood, seed=rng.randrange(2 ** 31), now=when)
    trial_id = start["trial_id"]
    item = _server_item(db, trial_id)
    t = when
    while True:
        response, rt, focus_lost, confidence = user.respond(item)
        t = t + timedelta(milliseconds=rt) + timedelta(seconds=1)
        result = engine.answer(db, start["session_id"], trial_id, response, rt, focus_lost, confidence, now=t)
        if result["done"]:
            break
        trial_id = result["trial_id"]
        item = _server_item(db, trial_id)
    actual = sum(1 for r in db.execute(
        "SELECT correct FROM trial WHERE session_id = ?", (start["session_id"],)).fetchall() if r["correct"])
    n = db.execute("SELECT COUNT(*) AS c FROM trial WHERE session_id = ?", (start["session_id"],)).fetchone()["c"]
    estimate = max(0, min(n, actual + rng.choice([-2, -1, -1, 0, 0, 1, 1, 2])))
    return engine.finish_session(db, start["session_id"], self_estimate=estimate, now=t)


def _server_item(db, trial_id):
    import json
    row = db.execute("SELECT item_json FROM trial WHERE id = ?", (trial_id,)).fetchone()
    return json.loads(row["item_json"])


def build_demo_profile(db, seed=2026, now=None):
    now = now or utcnow()
    rng = random.Random(seed)
    start = now - timedelta(days=DAYS_BACK)
    profile_id = engine.create_profile(
        db, dict(store=True, llm=False, voice=False), retention_days=30, is_demo=True, now=start,
    )
    db.execute("PRAGMA synchronous = OFF")
    user = sim.SimUser(START_THETAS, seed=seed, overconfidence=0.07, lapse=0.02, rushed=0.01)

    # Week one: a baseline check-in on every skill.
    day = start
    for dim in DIMENSION_KEYS:
        _run_session(db, profile_id, user, dim, "assess", day + timedelta(hours=rng.randint(9, 20)), rng)
        day += timedelta(hours=14)
    planner.refresh_plan(db, profile_id, now=day)

    # A goal set after the baseline, so the plan responds to it.
    twin.add_goal(db, profile_id, "working_memory", 65.0, iso(now + timedelta(days=14)), now=day)
    twin.add_goal(db, profile_id, "cognitive_flexibility", 60.0, iso(now + timedelta(days=21)), now=day)

    # Then roughly every other day: follow the top of the live plan, and practice raises true ability.
    day += timedelta(days=1)
    rounds_done = 0
    while day < now - timedelta(hours=6):
        plan = planner.refresh_plan(db, profile_id, now=day)
        for session in plan["days"][0]["sessions"]:
            dim = session["dimension"]
            when = day + timedelta(hours=rng.randint(7, 21), minutes=rng.randint(0, 59))
            if when >= now:
                when = now - timedelta(minutes=rng.randint(10, 300))
            mood = "tired" if rng.random() < 0.08 else None
            _run_session(db, profile_id, user, dim, session["mode"], when, rng, mood=mood)
            user.thetas[dim] += GROWTH_PER_PRACTICE * (1 + rng.random())
        if rounds_done < 6 and rng.random() < 0.4:
            scenario = collab.SCENARIOS[rounds_done]
            persona = "average_user" if rounds_done < 3 else "careful_partner"
            events = collab.simulate_persona_events(scenario, persona, rng)
            collab.record_round(db, profile_id, scenario["id"], events, now=day + timedelta(hours=2))
            rounds_done += 1
        day += timedelta(days=rng.choice([1, 2, 2, 3]))
    planner.refresh_plan(db, profile_id, now=now)
    db.execute("PRAGMA synchronous = NORMAL")
    db.commit()
    return profile_id
