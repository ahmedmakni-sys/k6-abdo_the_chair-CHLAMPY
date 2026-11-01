"""Assessment and training sessions: item selection, scoring, evidence and history."""

import json
import random
import uuid
from datetime import timedelta

from . import behaviour, estimator as est, items, storage
from .dimensions import DIMENSION_KEYS, METACOGNITION_POOL, TASKS_BY_DIMENSION, dimension_for_task
from .estimator import Posterior
from .storage import dumps, iso, parse_iso, utcnow

# Block plan per dimension: (task, trials). Two tasks reduce dependence on one format.
BLOCKS = {
    "attention": [("flanker", 8), ("gonogo", 8)],
    "working_memory": [("digit_span", 4), ("reverse_span", 4)],
    "processing_speed": [("same_different", 7), ("symbol_match", 7)],
    "logical_reasoning": [("number_series", 5), ("syllogism", 5)],
    "cognitive_flexibility": [("rule_switch", 8), ("colour_shape_shift", 8)],
    "verbal_reasoning": [("analogy", 5), ("odd_word", 5)],
    "spatial_reasoning": [("rotation", 5), ("mirror", 5)],
    "decision_making": [("expected_value", 6), ("base_rate", 6)],
    "creative_thinking": [("alt_uses", 1), ("word_link", 4)],
    "metacognition": [("mixed", 8)],
}

# Assessment can stop early once the estimate is this tight and both tasks have been seen.
STOP_SD = 0.5
# Self-monitoring evidence: confidence ratings carry less weight than task outcomes.
CONFIDENCE_WEIGHT = 0.6
MOODS = ("energised", "ok", "tired", "frustrated")


class SessionError(ValueError):
    pass


def _load_posterior(db, profile_id, dimension):
    row = db.execute(
        "SELECT grid_json, updated_at, n_trials FROM dim_state WHERE profile_id = ? AND dimension = ?",
        (profile_id, dimension),
    ).fetchone()
    if row is None:
        return Posterior(), None, 0
    return Posterior.from_list(json.loads(row["grid_json"])), row["updated_at"], row["n_trials"]


def _save_posterior(db, profile_id, dimension, posterior, now, n_trials):
    db.execute(
        "INSERT INTO dim_state (profile_id, dimension, grid_json, updated_at, n_trials) VALUES (?,?,?,?,?) "
        "ON CONFLICT(profile_id, dimension) DO UPDATE SET grid_json=excluded.grid_json, "
        "updated_at=excluded.updated_at, n_trials=excluded.n_trials",
        (profile_id, dimension, dumps(posterior.to_list()), iso(now), n_trials),
    )


def current_posterior(db, profile_id, dimension, now=None):
    """The posterior as of now, including uncertainty added by elapsed time."""
    now = now or utcnow()
    posterior, updated_at, n_trials = _load_posterior(db, profile_id, dimension)
    if updated_at:
        days = max(0.0, (now - parse_iso(updated_at)).total_seconds() / 86400.0)
        posterior.drift(est.DRIFT_VAR_PER_DAY * days)
    return posterior, n_trials


def _task_for_index(dimension, i, rng):
    remaining = i
    for task, count in BLOCKS[dimension]:
        if remaining < count:
            if task == "mixed":
                return rng.choice(METACOGNITION_POOL)
            return task
        remaining -= count
    return None


def _max_trials(dimension):
    return sum(count for _, count in BLOCKS[dimension])


def _min_trials(dimension):
    blocks = BLOCKS[dimension]
    return blocks[0][1] + min(2, blocks[-1][1]) if len(blocks) > 1 else blocks[0][1]


def _new_item(db, profile_id, session_row_id, dimension, state, rng, now):
    task = _task_for_index(dimension, state["i"], rng)
    task_dim = dimension_for_task(task)
    posterior, _, _ = _load_posterior(db, profile_id, task_dim)
    params = items.TASK_PARAMS[task]
    if state["mode"] == "assess" and dimension != "metacognition":
        level = est.choose_level_for_information(posterior, params["a"], params["c"], rng)
    elif dimension == "metacognition":
        # Items near 60% success give confidence ratings the most to work with.
        level = est.choose_level_for_success(posterior, params["a"], params["c"], target=0.6)
    else:
        level = est.choose_level_for_success(posterior, params["a"], params["c"], target=state["target"])
    ctx = state["ctx"].setdefault(task, {})
    item = items.generate(task, level, rng, ctx)
    ctx.update(item.pop("ctx_update", {}))
    # Reasoning items ask for a confidence rating; on self-monitoring sessions it is required.
    item["ask_confidence"] = item["kind"] == "mcq"
    item["confidence_required"] = dimension == "metacognition"
    cur = db.execute(
        "INSERT INTO trial (session_id, profile_id, dimension, task, level, item_json, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (session_row_id, profile_id, task_dim, task, item["level"], dumps(item), iso(now)),
    )
    return cur.lastrowid, item


def start_session(db, profile_id, dimension, mode="assess", mood=None, seed=None, now=None):
    now = now or utcnow()
    if not isinstance(dimension, str) or dimension not in DIMENSION_KEYS:
        raise SessionError("Unknown dimension")
    if mode not in ("assess", "train"):
        raise SessionError("Mode must be assess or train")
    if db.execute("SELECT 1 FROM profile WHERE id = ?", (profile_id,)).fetchone() is None:
        raise SessionError("Unknown profile")

    close_open_sessions(db, profile_id, now)
    mood = mood if mood in MOODS else None

    # Add the uncertainty that accumulated since this dimension was last seen.
    dims = {dimension} | ({"metacognition"} if dimension != "metacognition" else set())
    if dimension == "metacognition":
        dims |= {dimension_for_task(t) for t in METACOGNITION_POOL}
    for dim in dims:
        posterior, updated_at, n_trials = _load_posterior(db, profile_id, dim)
        if updated_at:
            days = max(0.0, (now - parse_iso(updated_at)).total_seconds() / 86400.0)
            posterior.drift(est.DRIFT_VAR_PER_DAY * days + est.DRIFT_VAR_PER_SESSION)
            _save_posterior(db, profile_id, dim, posterior, now, n_trials)

    session_id = uuid.uuid4().hex
    seed = seed if seed is not None else random.randrange(2 ** 31)
    rng = random.Random(seed)
    state = dict(
        i=0, mode=mode, ctx={}, seed=seed, target=behaviour.success_target(mood),
        responses=[], rts=[], draws=0,
    )
    before = {}
    for dim in dims:
        posterior, _, _ = _load_posterior(db, profile_id, dim)
        before[dim] = posterior.summary()
    state["before"] = before
    db.execute(
        "INSERT INTO session (id, profile_id, dimension, mode, mood, started_at, state_json) VALUES (?,?,?,?,?,?,?)",
        (session_id, profile_id, dimension, mode, mood, iso(now), dumps(state)),
    )
    trial_id, item = _new_item(db, profile_id, session_id, dimension, state, rng, now)
    state["draws"] = 1
    db.execute("UPDATE session SET state_json = ? WHERE id = ?", (dumps(state), session_id))
    db.execute("UPDATE profile SET last_active_at = ? WHERE id = ?", (iso(now), profile_id))
    db.commit()
    return dict(
        session_id=session_id, dimension=dimension, mode=mode,
        max_trials=_max_trials(dimension),
        trial_id=trial_id, item=items.client_view(item),
    )


def _coerce_rt(rt_ms):
    try:
        rt = float(rt_ms)
    except (TypeError, ValueError):
        return None
    if rt != rt or rt < 0:  # NaN or negative
        return None
    return min(rt, 600000.0)


def _coerce_confidence(confidence):
    if confidence is None:
        return None
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return None
    if c != c:
        return None
    return max(0.0, min(1.0, c))


def _coerce_response(response):
    if response is None:
        return None
    if isinstance(response, (dict, list)):
        return None
    return str(response)[:2000]


def answer(db, session_id, trial_id, response, rt_ms=None, focus_lost=False, confidence=None, now=None):
    now = now or utcnow()
    if not isinstance(trial_id, int) or isinstance(trial_id, bool):
        raise SessionError("Unknown trial")
    session = db.execute("SELECT * FROM session WHERE id = ?", (session_id,)).fetchone()
    if session is None:
        raise SessionError("Unknown session")
    if session["ended_at"]:
        raise SessionError("This session has already finished")
    row = db.execute("SELECT * FROM trial WHERE id = ? AND session_id = ?", (trial_id, session_id)).fetchone()
    if row is None:
        raise SessionError("Unknown trial")
    if row["answered_at"]:
        raise SessionError("This item has already been answered")

    item = json.loads(row["item_json"])
    state = json.loads(session["state_json"])
    profile_id, task_dim = session["profile_id"], row["dimension"]
    response = _coerce_response(response)
    rt_ms = _coerce_rt(rt_ms)
    confidence = _coerce_confidence(confidence)

    scored = items.score_response(item, response, rt_ms)
    weight, flags = behaviour.trial_weight(
        item, rt_ms, bool(focus_lost), state["responses"], state["rts"], scored["timed_out"]
    )
    weight = min(weight, items.TASK_PARAMS[item["task"]]["cap"])

    posterior, _, n_trials = _load_posterior(db, profile_id, task_dim)
    pct_before = posterior.pct()
    posterior.update(item["a"], item["b"], item["c"], scored["y"], weight)
    pct_after = posterior.pct()
    _save_posterior(db, profile_id, task_dim, posterior, now, n_trials + 1)

    if confidence is not None and item.get("ask_confidence"):
        meta_post, _, meta_n = _load_posterior(db, profile_id, "metacognition")
        outcome = 1.0 if scored["correct"] else 0.0
        y_meta = max(0.0, 1.0 - 2.0 * (confidence - outcome) ** 2)
        meta_post.update(1.0, 0.0, 0.0, y_meta, CONFIDENCE_WEIGHT * weight)
        _save_posterior(db, profile_id, "metacognition", meta_post, now, meta_n + 1)

    db.execute(
        "UPDATE trial SET response_json=?, correct=?, y=?, w=?, rt_ms=?, flags_json=?, confidence=?, "
        "pct_before=?, pct_after=?, answered_at=? WHERE id=?",
        (dumps(response), int(scored["correct"]), scored["y"], weight, rt_ms, dumps(flags), confidence,
         round(pct_before, 2), round(pct_after, 2), iso(now), trial_id),
    )

    state["i"] += 1
    state["responses"].append(response if response is not None else "")
    if rt_ms is not None:
        state["rts"].append(rt_ms)

    dimension = session["dimension"]
    done = state["i"] >= _max_trials(dimension)
    if (not done and state["mode"] == "assess" and dimension != "metacognition"
            and state["i"] >= _min_trials(dimension) and posterior.sd() < STOP_SD):
        done = True

    # Items derive from the seed and draw count, so a session can be replayed and audited.
    rng = random.Random(f"{state['seed']}:{state['i']}")
    next_trial, next_item = None, None
    if not done:
        trials = _session_trials(db, session_id)
        proxy = behaviour.state_proxy(behaviour.session_stats(trials), session["mood"])
        state["target"] = behaviour.success_target(session["mood"], proxy)
        next_trial, next_item = _new_item(db, profile_id, session_id, dimension, state, rng, now)
    db.execute("UPDATE session SET state_json = ? WHERE id = ?", (dumps(state), session_id))
    db.commit()

    return dict(
        correct=bool(scored["correct"]),
        timed_out=scored["timed_out"],
        detail=scored["detail"],
        flags=flags,
        weight=weight,
        answer=None if item["task"] == "alt_uses" else _display_answer(item),
        live=dict(dimension=task_dim, **posterior.summary()),
        done=done,
        progress=dict(i=state["i"], max=_max_trials(dimension)),
        trial_id=next_trial,
        item=items.client_view(next_item) if next_item else None,
    )


def _display_answer(item):
    if item["task"] == "word_link":
        return item["answer"][0]
    labels = item.get("payload", {}).get("option_labels")
    return labels.get(item["answer"], item["answer"]) if labels else item["answer"]


def _session_trials(db, session_id):
    rows = db.execute(
        "SELECT * FROM trial WHERE session_id = ? AND answered_at IS NOT NULL ORDER BY id", (session_id,)
    ).fetchall()
    return [_trial_dict(r) for r in rows]


def _trial_dict(row):
    item = json.loads(row["item_json"])
    return dict(
        id=row["id"], task=row["task"], dimension=row["dimension"], level=row["level"],
        correct=bool(row["correct"]) if row["correct"] is not None else None,
        y=row["y"], w=row["w"], rt_ms=row["rt_ms"],
        flags=json.loads(row["flags_json"]) if row["flags_json"] else [],
        confidence=row["confidence"],
        deadline_ms=item.get("deadline_ms"), speeded=item.get("speeded"),
        meta=item.get("meta", {}), kind=item.get("kind"),
        pct_before=row["pct_before"], pct_after=row["pct_after"],
        answered_at=row["answered_at"], session_id=row["session_id"],
        prompt=item.get("prompt"),
    )


def finish_session(db, session_id, self_estimate=None, now=None):
    """Close a session, record evidence and snapshots, and return what changed and why."""
    now = now or utcnow()
    session = db.execute("SELECT * FROM session WHERE id = ?", (session_id,)).fetchone()
    if session is None:
        raise SessionError("Unknown session")
    if session["ended_at"]:
        return json.loads(session["summary_json"])
    profile_id = session["profile_id"]
    state = json.loads(session["state_json"])
    db.execute("DELETE FROM trial WHERE session_id = ? AND answered_at IS NULL", (session_id,))
    trials = _session_trials(db, session_id)
    stats = behaviour.session_stats(trials)
    proxy = behaviour.state_proxy(stats, session["mood"])

    if self_estimate is not None and trials:
        try:
            estimate = max(0, min(len(trials), int(self_estimate)))
        except (TypeError, ValueError):
            estimate = None
        if estimate is not None:
            actual = sum(1 for t in trials if t["correct"])
            meta_post, _, meta_n = _load_posterior(db, profile_id, "metacognition")
            meta_post.update(1.0, 0.0, 0.0, 1.0 - abs(estimate - actual) / len(trials), 1.0)
            _save_posterior(db, profile_id, "metacognition", meta_post, now, meta_n + 1)
            stats["self_estimate"] = estimate
            stats["actual_correct"] = actual

    touched = {t["dimension"] for t in trials}
    if any(t.get("confidence") is not None for t in trials) or stats.get("self_estimate") is not None:
        touched.add("metacognition")
    changes = {}
    for dim in sorted(touched):
        posterior, _, n_trials = _load_posterior(db, profile_id, dim)
        s = posterior.summary()
        db.execute(
            "INSERT INTO snapshot (profile_id, dimension, at, theta, theta_sd, pct, low, high, n_trials, session_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (profile_id, dim, iso(now), s["theta"], s["theta_sd"], s["pct"], s["low"], s["high"], n_trials, session_id),
        )
        changes[dim] = dict(before=state["before"].get(dim), after=s, n_trials=n_trials)

    summary = dict(
        session_id=session_id, dimension=session["dimension"], mode=session["mode"], stats=stats,
        state_proxy=proxy, changes=changes, top_evidence=_top_evidence(trials),
    )
    db.execute(
        "UPDATE session SET ended_at = ?, summary_json = ? WHERE id = ?", (iso(now), dumps(summary), session_id)
    )
    db.execute("UPDATE profile SET last_active_at = ? WHERE id = ?", (iso(now), profile_id))
    db.commit()
    return summary


def close_open_sessions(db, profile_id, now=None):
    """Sessions abandoned mid-way still count: their answered items stay in the history."""
    rows = db.execute(
        "SELECT id FROM session WHERE profile_id = ? AND ended_at IS NULL", (profile_id,)
    ).fetchall()
    for row in rows:
        finish_session(db, row["id"], now=now)


def _top_evidence(trials, k=5):
    """Trials that moved the estimate most, used by the 'why did this change' explanation."""
    moved = [t for t in trials if t.get("pct_before") is not None]
    moved.sort(key=lambda t: -abs((t["pct_after"] or 0) - (t["pct_before"] or 0)))
    return [
        dict(
            task=t["task"], level=t["level"], correct=t["correct"], rt_ms=t["rt_ms"], weight=t["w"],
            moved=round(t["pct_after"] - t["pct_before"], 1), flags=t["flags"], prompt=t.get("prompt"),
        )
        for t in moved[:k]
    ]


def dimension_trials(db, profile_id, dimension, limit=400):
    rows = db.execute(
        "SELECT * FROM trial WHERE profile_id = ? AND dimension = ? AND answered_at IS NOT NULL "
        "ORDER BY answered_at DESC, id DESC LIMIT ?",
        (profile_id, dimension, limit),
    ).fetchall()
    return [_trial_dict(r) for r in rows]


def create_profile(db, consent, retention_days=180, is_demo=False, now=None):
    now = now or utcnow()
    if not isinstance(consent, dict) or not consent.get("store"):
        raise SessionError("Consent to store results on this device is required to continue")
    try:
        retention = int(retention_days)
    except (TypeError, ValueError):
        retention = 180
    retention = max(7, min(730, retention))
    profile_id = uuid.uuid4().hex
    clean = dict(
        store=True, llm=bool(consent.get("llm")), voice=bool(consent.get("voice")),
        accepted_at=iso(now), version=1,
    )
    db.execute(
        "INSERT INTO profile (id, created_at, consent_json, retention_days, is_demo, last_active_at) VALUES (?,?,?,?,?,?)",
        (profile_id, iso(now), dumps(clean), retention, int(is_demo), iso(now)),
    )
    db.commit()
    return profile_id
