"""The Brain Twin: a dynamic, historised profile with honest uncertainty.

History is mandatory and comes from immutable snapshots. Projections are optional and
always returned as ranges: with too little history the projection refuses to appear.
"""

import json
from collections import defaultdict
from datetime import timedelta
from statistics import NormalDist

import numpy as np

from . import behaviour, engine, estimator as est
from .dimensions import DIMENSION_KEYS, DIMENSIONS
from .storage import iso, parse_iso, utcnow

MIN_PROJECTION_POINTS = 3
PROJECTION_DAYS = [7, 14, 30]
# Prior on growth per day in theta units: gentle improvement, mostly unknown.
SLOPE_PRIOR_MEAN = 0.004
SLOPE_PRIOR_SD = 0.02


def evidence_label(width, n_trials):
    if n_trials == 0:
        return "no evidence yet"
    if width >= 45:
        return "early estimate"
    if width >= 28:
        return "moderate evidence"
    return "strong evidence"


def profile_view(db, profile_id, now=None):
    """Current state of every dimension, including uncertainty added by elapsed time."""
    now = now or utcnow()
    last_snaps = {}
    prev_snaps = {}
    for row in db.execute(
        "SELECT * FROM snapshot WHERE profile_id = ? ORDER BY at, id", (profile_id,)
    ).fetchall():
        if row["dimension"] in last_snaps:
            prev_snaps[row["dimension"]] = last_snaps[row["dimension"]]
        last_snaps[row["dimension"]] = row

    out = []
    for dim in DIMENSION_KEYS:
        posterior, n_trials = engine.current_posterior(db, profile_id, dim, now)
        s = posterior.summary()
        width = s["high"] - s["low"]
        last = last_snaps.get(dim)
        prev = prev_snaps.get(dim)
        days_since = None
        if last is not None:
            days_since = round((now - parse_iso(last["at"])).total_seconds() / 86400.0, 1)
        change = None
        if last is not None and prev is not None:
            change = dict(
                delta=round(last["pct"] - prev["pct"], 1),
                prob_up=round(prob_improved(prev["theta"], prev["theta_sd"], last["theta"], last["theta_sd"]), 3),
            )
        out.append(dict(
            key=dim,
            name=DIMENSIONS[dim]["name"],
            plain=DIMENSIONS[dim]["plain"],
            pct=s["pct"], low=s["low"], high=s["high"],
            theta=s["theta"], theta_sd=s["theta_sd"],
            width=round(width, 1), n_trials=n_trials,
            evidence=evidence_label(width, n_trials),
            days_since=days_since, change=change,
        ))
    return out


def prob_improved(theta_a, sd_a, theta_b, sd_b):
    """Probability that b exceeds a, treating estimates as independent normals."""
    spread = (sd_a ** 2 + sd_b ** 2) ** 0.5
    if spread == 0:
        return 0.5
    return NormalDist().cdf((theta_b - theta_a) / spread)


def history(db, profile_id):
    by_dim = defaultdict(list)
    for row in db.execute(
        "SELECT dimension, at, theta, theta_sd, pct, low, high, n_trials FROM snapshot "
        "WHERE profile_id = ? ORDER BY at, id", (profile_id,)
    ).fetchall():
        by_dim[row["dimension"]].append(dict(
            at=row["at"], theta=row["theta"], theta_sd=row["theta_sd"], pct=row["pct"],
            low=row["low"], high=row["high"], n_trials=row["n_trials"],
        ))
    return dict(by_dim)


def project(points, now):
    """Bayesian linear trend on theta. Returns ranges; refuses when history is too short.

    The result answers 'where might this be if practice continues in a similar way?'
    It is never a statement about what will happen.
    """
    if len(points) < MIN_PROJECTION_POINTS:
        return dict(available=False, reason=f"Needs at least {MIN_PROJECTION_POINTS} check-ins. Keep going and a range will appear.")
    t0 = parse_iso(points[0]["at"])
    days = np.array([(parse_iso(p["at"]) - t0).total_seconds() / 86400.0 for p in points])
    if days.max() - days.min() < 3:
        return dict(available=False, reason="Needs check-ins spread over at least 3 days.")
    y = np.array([p["theta"] for p in points])
    noise = np.array([p["theta_sd"] ** 2 + est.DRIFT_VAR_PER_SESSION for p in points])

    # Conjugate update for intercept and slope with a Gaussian prior.
    X = np.column_stack([np.ones_like(days), days])
    prior_prec = np.diag([1.0 / 3.0 ** 2, 1.0 / SLOPE_PRIOR_SD ** 2])
    prior_mean = np.array([y.mean(), SLOPE_PRIOR_MEAN])
    W = np.diag(1.0 / noise)
    post_cov = np.linalg.inv(prior_prec + X.T @ W @ X)
    post_mean = post_cov @ (prior_prec @ prior_mean + X.T @ W @ y)

    now_day = (now - t0).total_seconds() / 86400.0
    ranges = []
    for horizon in PROJECTION_DAYS:
        day = now_day + horizon
        x = np.array([1.0, day])
        mean = float(x @ post_mean)
        var = float(x @ post_cov @ x) + est.DRIFT_VAR_PER_DAY * horizon
        sd = var ** 0.5
        norm = NormalDist(mean, sd)
        ranges.append(dict(
            days=horizon,
            at=iso(now + timedelta(days=horizon)),
            pct=round(float(est.theta_to_pct(mean)), 1),
            low90=round(float(est.theta_to_pct(norm.inv_cdf(0.05))), 1),
            high90=round(float(est.theta_to_pct(norm.inv_cdf(0.95))), 1),
            low50=round(float(est.theta_to_pct(norm.inv_cdf(0.25))), 1),
            high50=round(float(est.theta_to_pct(norm.inv_cdf(0.75))), 1),
        ))
    slope = float(post_mean[1])
    slope_sd = float(post_cov[1, 1] ** 0.5)
    return dict(
        available=True,
        ranges=ranges,
        prob_growing=round(1.0 - NormalDist(slope, slope_sd).cdf(0.0), 3),
        wording="A plausible range if practice continues in a similar way. This is not a prediction of what will happen.",
    )


def heatmaps(db, profile_id, now=None, weeks=8):
    """Two heatmaps: estimate by week, and observed success by difficulty level."""
    now = now or utcnow()
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
    starts = [week_start - timedelta(weeks=i) for i in reversed(range(weeks))]
    labels = [s.strftime("%d %b") for s in starts]
    by_week = {d: [None] * weeks for d in DIMENSION_KEYS}
    trials_by_week = {d: [0] * weeks for d in DIMENSION_KEYS}
    for row in db.execute(
        "SELECT dimension, at, pct FROM snapshot WHERE profile_id = ? ORDER BY at, id", (profile_id,)
    ).fetchall():
        at = parse_iso(row["at"])
        for i, start in enumerate(starts):
            if start <= at < start + timedelta(weeks=1):
                by_week[row["dimension"]][i] = row["pct"]

    level_counts = {d: [[0, 0] for _ in range(est.LEVELS)] for d in DIMENSION_KEYS}
    for row in db.execute(
        "SELECT dimension, level, correct, answered_at FROM trial WHERE profile_id = ? AND answered_at IS NOT NULL",
        (profile_id,),
    ).fetchall():
        level_counts[row["dimension"]][row["level"] - 1][0] += row["correct"] or 0
        level_counts[row["dimension"]][row["level"] - 1][1] += 1
        at = parse_iso(row["answered_at"])
        for i, start in enumerate(starts):
            if start <= at < start + timedelta(weeks=1):
                trials_by_week[row["dimension"]][i] += 1
    by_level = {
        d: [dict(rate=round(c[0] / c[1], 3) if c[1] else None, n=c[1]) for c in level_counts[d]]
        for d in DIMENSION_KEYS
    }
    return dict(week_labels=labels, by_week=by_week, trials_by_week=trials_by_week, by_level=by_level)


def goals_view(db, profile_id, now=None):
    now = now or utcnow()
    out = []
    for row in db.execute("SELECT * FROM goal WHERE profile_id = ? ORDER BY created_at", (profile_id,)).fetchall():
        posterior, _ = engine.current_posterior(db, profile_id, row["dimension"], now)
        prob = posterior.prob_at_least(row["target_pct"])
        s = posterior.summary()
        due = parse_iso(row["due_date"])
        days_left = (due - now).total_seconds() / 86400.0
        span = max(row["target_pct"] - row["start_pct"], 1.0)
        progress = max(0.0, min(1.0, (s["pct"] - row["start_pct"]) / span))
        if prob >= 0.8:
            status = "reached"
        elif days_left < 0:
            status = "past due"
        else:
            status = "on the way" if prob >= 0.3 or progress >= 0.5 else "needs attention"
        out.append(dict(
            id=row["id"], dimension=row["dimension"], name=DIMENSIONS[row["dimension"]]["name"],
            target_pct=row["target_pct"], start_pct=row["start_pct"], due_date=row["due_date"],
            current_pct=s["pct"], low=s["low"], high=s["high"],
            prob_reached=round(prob, 3), progress=round(progress, 3),
            days_left=round(days_left, 1), status=status,
        ))
    return out


def add_goal(db, profile_id, dimension, target_pct, due_date, now=None):
    now = now or utcnow()
    if dimension not in DIMENSION_KEYS:
        raise engine.SessionError("Unknown dimension")
    try:
        target = float(target_pct)
    except (TypeError, ValueError):
        raise engine.SessionError("Target must be a number from 1 to 99")
    if not 1 <= target <= 99:
        raise engine.SessionError("Target must be a number from 1 to 99")
    try:
        due = parse_iso(due_date)
    except (TypeError, ValueError):
        raise engine.SessionError("Due date must be an ISO date")
    if due.tzinfo is None:
        due = due.replace(tzinfo=now.tzinfo)
    posterior, _ = engine.current_posterior(db, profile_id, dimension, now)
    cur = db.execute(
        "INSERT INTO goal (profile_id, dimension, target_pct, due_date, created_at, start_pct) VALUES (?,?,?,?,?,?)",
        (profile_id, dimension, target, iso(due), iso(now), round(posterior.pct(), 1)),
    )
    db.commit()
    return cur.lastrowid


def recent_session_stats(db, profile_id, limit=30):
    rows = db.execute(
        "SELECT dimension, mode, ended_at, summary_json FROM session "
        "WHERE profile_id = ? AND ended_at IS NOT NULL ORDER BY ended_at DESC LIMIT ?",
        (profile_id, limit),
    ).fetchall()
    return [
        dict(dimension=r["dimension"], mode=r["mode"], ended_at=r["ended_at"],
             stats=json.loads(r["summary_json"])["stats"],
             state_proxy=json.loads(r["summary_json"])["state_proxy"])
        for r in rows
    ]
