"""Adaptive learning plan. Every recommendation exposes its reasons and arithmetic.

Priority for each dimension is a weighted sum of four components in [0, 1]:

    priority = 0.35 goal_gap + 0.25 uncertainty + 0.20 staleness + 0.20 plateau

Plans are versioned, so the app can show how and why the plan changed.
"""

import json
import math
from datetime import timedelta

from . import estimator as est, items, twin
from .dimensions import DIMENSION_KEYS, DIMENSIONS, TASKS_BY_DIMENSION
from .storage import dumps, iso, utcnow
from .engine import _load_posterior, BLOCKS

WEIGHTS = dict(goal_gap=0.35, uncertainty=0.25, staleness=0.20, plateau=0.20)
SESSIONS_PER_DAY = 2
PLAN_DAYS = 7
# Within a day, a chosen dimension's priority drops by this factor so sessions interleave.
SPACING_DECAY = 0.45
# How long a session takes, in minutes, for planning purposes.
MINUTES = {
    "attention": 4, "working_memory": 4, "processing_speed": 3, "logical_reasoning": 6,
    "cognitive_flexibility": 4, "verbal_reasoning": 4, "spatial_reasoning": 6,
    "decision_making": 6, "creative_thinking": 5, "metacognition": 6,
}


def priorities(view, goals, hist):
    """Return each dimension's priority and the components behind it."""
    goal_by_dim = {}
    for g in goals:
        if g["status"] != "reached":
            goal_by_dim[g["dimension"]] = max(goal_by_dim.get(g["dimension"], 0.0), g["target_pct"])

    rows = []
    for d in view:
        target = goal_by_dim.get(d["key"])
        # An unreached goal always counts for at least half, so it stays visible in the plan.
        goal_gap = 0.5 + 0.5 * min(1.0, max(0.0, target - d["pct"]) / 30.0) if target else 0.0
        uncertainty = min(1.0, d["width"] / 70.0)
        staleness = 1.0 if d["days_since"] is None else 1.0 - math.exp(-d["days_since"] / 7.0)
        plateau = _plateau(hist.get(d["key"], []))
        comps = dict(
            goal_gap=round(goal_gap, 3), uncertainty=round(uncertainty, 3),
            staleness=round(staleness, 3), plateau=round(plateau, 3),
        )
        rows.append(dict(
            dimension=d["key"], name=d["name"],
            priority=round(sum(WEIGHTS[k] * comps[k] for k in WEIGHTS), 3),
            components=comps, target=target, reasons=_reasons(d, comps, target),
        ))
    rows.sort(key=lambda r: -r["priority"])
    return rows


def _plateau(points):
    """High when the last few check-ins show little movement; neutral with little history."""
    if len(points) < 3:
        return 0.5
    recent = points[-4:]
    change = recent[-1]["pct"] - recent[0]["pct"]
    return float(max(0.0, min(1.0, 1.0 - change / 8.0)))


def _reasons(d, comps, target):
    out = []
    if target and comps["goal_gap"] > 0:
        out.append(f"your goal of {target:.0f}% is {max(0.0, target - d['pct']):.0f} points above the current estimate")
    if d["n_trials"] == 0:
        out.append("there is no evidence for this dimension yet")
    elif comps["uncertainty"] >= 0.5:
        out.append(f"the range is still wide ({d['low']:.0f}% to {d['high']:.0f}%)")
    if d["days_since"] is not None and d["days_since"] >= 5:
        out.append(f"you last practised this {d['days_since']:.0f} days ago")
    if comps["plateau"] >= 0.8 and d["n_trials"] > 0:
        out.append("the last few check-ins show little change")
    if not out:
        out.append("it keeps this skill in rotation with the others")
    return out


def _session_for(db, profile_id, row, view_by_key):
    """Decide mode and level for one planned session."""
    dim = row["dimension"]
    d = view_by_key[dim]
    mode = "assess" if d["width"] >= 45 else "train"
    level = None
    if dim != "metacognition":
        task = BLOCKS[dim][0][0]
        params = items.TASK_PARAMS[task]
        posterior, _, _ = _load_posterior(db, profile_id, dim)
        level = est.choose_level_for_success(posterior, params["a"], params["c"], target=0.8)
    return dict(
        dimension=dim, name=row["name"], mode=mode, level=level, minutes=MINUTES[dim],
        priority=row["priority"], components=row["components"], why=row["reasons"],
        success_measure=_success_measure(mode, d, level),
    )


def _success_measure(mode, d, level):
    if mode == "assess":
        return f"Range narrows to under 45 points (now {d['width']:.0f})."
    if level:
        return f"About 8 in 10 right at level {level} or above, with the lower bound above {d['low']:.0f}%."
    return f"Lower bound of the range rises above {d['low']:.0f}%."


def build_plan(db, profile_id, now=None):
    now = now or utcnow()
    view = twin.profile_view(db, profile_id, now)
    goals = twin.goals_view(db, profile_id, now)
    hist = twin.history(db, profile_id)
    ranked = priorities(view, goals, hist)
    by_key = {d["key"]: d for d in view}
    scores = {r["dimension"]: r["priority"] for r in ranked}
    row_by_dim = {r["dimension"]: r for r in ranked}

    days = []
    last_seen = {}
    for offset in range(PLAN_DAYS):
        date = (now + timedelta(days=offset)).date().isoformat()
        chosen, used = [], set()
        for _ in range(SESSIONS_PER_DAY):
            # Spacing: a dimension scheduled recently is discounted, so practice interleaves.
            adjusted = {}
            for dim, base in scores.items():
                if dim in used:
                    continue
                gap = offset - last_seen.get(dim, -99)
                adjusted[dim] = base * (SPACING_DECAY ** max(0, 3 - gap))
            pick = max(adjusted, key=adjusted.get)
            used.add(pick)
            last_seen[pick] = offset
            chosen.append(_session_for(db, profile_id, row_by_dim[pick], by_key))
        days.append(dict(date=date, sessions=chosen))

    plan = dict(
        created_at=iso(now), weights=WEIGHTS, days=days, ranked=ranked,
        milestones=_milestones(view, goals, now),
    )
    return plan


def _milestones(view, goals, now):
    """Two-week, measurable targets. Goals come first, then the strongest growth candidates."""
    out = []
    goal_dims = set()
    for g in goals:
        goal_dims.add(g["dimension"])
        out.append(dict(
            dimension=g["dimension"], name=g["name"], source="your goal",
            from_pct=g["current_pct"], to_pct=g["target_pct"], due=g["due_date"],
            measure=f"At least 80% probability of being at or above {g['target_pct']:.0f}%",
            prob_now=g["prob_reached"],
        ))
    assessed = [d for d in view if d["n_trials"] > 0 and d["key"] not in goal_dims]
    assessed.sort(key=lambda d: d["pct"])
    for d in assessed[:3]:
        target = min(95.0, d["pct"] + 5.0)
        out.append(dict(
            dimension=d["key"], name=d["name"], source="suggested",
            from_pct=d["pct"], to_pct=round(target, 1),
            due=iso(now + timedelta(days=14)),
            measure=f"Estimate reaches {target:.0f}% with the lower bound above {d['low']:.0f}%",
            prob_now=None,
        ))
    return out


def diff_plans(old, new):
    """Explain what changed between two plan versions, in plain language."""
    if not old:
        return ["This is your first plan. It starts with whatever is least known."]
    old_top = [r["dimension"] for r in old["ranked"][:3]]
    new_top = [r["dimension"] for r in new["ranked"][:3]]
    notes = []
    for dim in new_top:
        if dim not in old_top:
            row = next(r for r in new["ranked"] if r["dimension"] == dim)
            notes.append(f"{DIMENSIONS[dim]['name']} moved up because {row['reasons'][0]}.")
    for dim in old_top:
        if dim not in new_top:
            row = next(r for r in new["ranked"] if r["dimension"] == dim)
            notes.append(
                f"{DIMENSIONS[dim]['name']} moved down: its priority is now {row['priority']:.2f}, "
                f"since recent evidence reduced its need for attention."
            )
    if not notes:
        notes.append("Your priorities held steady, so the order of focus is unchanged.")
    return notes


def latest_plan(db, profile_id):
    row = db.execute(
        "SELECT plan_json FROM plan WHERE profile_id = ? ORDER BY id DESC LIMIT 1", (profile_id,)
    ).fetchone()
    return json.loads(row["plan_json"]) if row else None


def refresh_plan(db, profile_id, now=None):
    """Build a new version and record what changed compared with the previous one."""
    now = now or utcnow()
    old = latest_plan(db, profile_id)
    new = build_plan(db, profile_id, now)
    new["changes"] = diff_plans(old, new)
    new["version"] = (old.get("version", 0) + 1) if old else 1
    db.execute(
        "INSERT INTO plan (profile_id, created_at, plan_json) VALUES (?,?,?)",
        (profile_id, iso(now), dumps(new)),
    )
    db.commit()
    return new


def plan_history(db, profile_id, limit=8):
    rows = db.execute(
        "SELECT plan_json, created_at FROM plan WHERE profile_id = ? ORDER BY id DESC LIMIT ?",
        (profile_id, limit),
    ).fetchall()
    out = []
    for row in rows:
        p = json.loads(row["plan_json"])
        out.append(dict(version=p.get("version"), created_at=row["created_at"], changes=p.get("changes", [])))
    return out
