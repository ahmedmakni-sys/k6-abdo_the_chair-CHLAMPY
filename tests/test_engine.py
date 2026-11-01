import json
import random

import numpy as np
import pytest

from ai4brain import engine, estimator as est, items, planner, sim, storage, twin
from ai4brain.dimensions import DIMENSION_KEYS, DIMENSIONS, TASKS_BY_DIMENSION
from ai4brain.engine import SessionError


@pytest.fixture
def db():
    conn = storage.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def profile(db):
    return engine.create_profile(db, dict(store=True))


# ---- estimator ---------------------------------------------------------------

def test_prior_is_centred_and_wide():
    p = est.Posterior()
    low, high = p.pct_interval()
    assert 45 < p.pct() < 55
    assert high - low > 50


def test_correct_answers_raise_and_errors_lower_the_estimate():
    up, down = est.Posterior(), est.Posterior()
    for _ in range(5):
        up.update(1.2, 0.0, 0.25, 1.0)
        down.update(1.2, 0.0, 0.25, 0.0)
    assert up.pct() > 60 > 40 > down.pct()


def test_evidence_narrows_the_interval():
    p = est.Posterior()
    width_before = np.subtract(*reversed(p.pct_interval()))
    for i in range(12):
        p.update(1.2, 0.0, 0.0, float(i % 2))
    width_after = np.subtract(*reversed(p.pct_interval()))
    assert width_after < width_before


def test_low_weight_moves_the_estimate_less():
    full, weak = est.Posterior(), est.Posterior()
    full.update(1.2, 0.0, 0.0, 1.0, 1.0)
    weak.update(1.2, 0.0, 0.0, 1.0, 0.25)
    assert abs(full.pct() - 50) > abs(weak.pct() - 50)


def test_drift_widens_without_moving_the_centre_much():
    p = est.Posterior()
    for i in range(20):
        p.update(1.2, 0.5, 0.0, float(i % 3 != 0))
    sd, mean = p.sd(), p.mean()
    p.drift(est.DRIFT_VAR_PER_DAY * 60)
    assert p.sd() > sd
    assert abs(p.mean() - mean) < 0.15


def test_pct_mapping_is_monotonic_and_bounded():
    assert (np.diff(est.PCT_GRID) > 0).all()
    assert 0 < est.PCT_GRID.min() and est.PCT_GRID.max() < 100


def test_posterior_survives_serialisation():
    p = est.Posterior()
    p.update(1.0, 0.3, 0.25, 1.0)
    q = est.Posterior.from_list(p.to_list())
    assert abs(p.pct() - q.pct()) < 0.01


# ---- items -------------------------------------------------------------------

ALL_TASKS = [t for tasks in TASKS_BY_DIMENSION.values() for t in tasks]


@pytest.mark.parametrize("task", ALL_TASKS)
@pytest.mark.parametrize("level", [1, 5, 10])
def test_every_generator_produces_valid_items(task, level):
    for seed in range(15):
        rng = random.Random(seed)
        item = items.generate(task, level, rng, {})
        assert 1 <= item["level"] <= 10
        assert item["dimension"] in DIMENSIONS
        view = items.client_view(item)
        assert "answer" not in view
        if item["kind"] == "mcq":
            options = item["payload"]["options"]
            assert len(options) >= 2 and len(set(options)) == len(options)
            assert str(item["answer"]) in [str(o) for o in options]


@pytest.mark.parametrize("task", ALL_TASKS)
def test_correct_response_scores_correct_and_wrong_scores_wrong(task):
    rng = random.Random(1)
    item = items.generate(task, 5, rng, {})
    if task == "alt_uses":
        good = items.score_response(item, "puppet theatre\nbird feeder\nrain gauge\nchess piece\nstencil\nwind chime", 20000)
        bad = items.score_response(item, "asdf\nqqq", 20000)
        assert good["y"] > bad["y"]
        return
    answer = item["answer"][0] if isinstance(item["answer"], list) else item["answer"]
    if item["kind"] == "go_nogo":
        answer = "go" if answer == "go" else None
    scored = items.score_response(item, answer, 100)
    assert scored["correct"] and scored["y"] > 0
    assert not items.score_response(item, "definitely wrong", 100)["correct"] or item["kind"] == "go_nogo"


def test_rotation_options_are_a_real_rotation_and_mirrors_are_not():
    for seed in range(40):
        rng = random.Random(seed)
        item = items.generate("rotation", rng.randint(1, 10), rng, {})
        size = item["payload"]["grid_size"]
        target = {tuple(c) for c in item["payload"]["target"]}
        rot_forms = {items._normal(r) for r in items._rotations(target, size)}
        right = next(o for o in item["payload"]["grid_options"] if o["id"] == item["answer"])
        assert items._normal({tuple(c) for c in right["cells"]}) in rot_forms
        for option in item["payload"]["grid_options"]:
            if option["id"] != item["answer"]:
                assert items._normal({tuple(c) for c in option["cells"]}) not in rot_forms


def test_mirror_answer_is_the_flip():
    for seed in range(40):
        rng = random.Random(seed)
        item = items.generate("mirror", rng.randint(1, 10), rng, {})
        size = item["payload"]["grid_size"]
        target = {tuple(c) for c in item["payload"]["target"]}
        right = next(o for o in item["payload"]["grid_options"] if o["id"] == item["answer"])
        assert items._normal({tuple(c) for c in right["cells"]}) == items._normal(items._flip(target, size))


def test_expected_value_answer_is_really_higher():
    for seed in range(60):
        rng = random.Random(seed)
        item = items.generate("expected_value", rng.randint(1, 10), rng, {})
        values = {}
        for key, label in item["payload"]["option_labels"].items():
            p, v = label.split("% chance of ")
            values[key] = float(p) * float(v.split()[0])
        assert values[item["answer"]] > min(values.values())


def test_number_series_rules_generate_the_shown_answer():
    for seed in range(40):
        rng = random.Random(seed)
        shown, next_term = items._series(rng.randint(1, 10), rng)
        assert len(shown) >= 5 and isinstance(next_term, int)


def test_gonogo_withholding_on_a_hold_trial_is_correct():
    for seed in range(40):
        item = items.generate("gonogo", 5, random.Random(seed), {})
        if item["answer"] == "hold":
            assert items.score_response(item, None, None)["correct"]
            assert not items.score_response(item, "go", 400)["correct"]
            return
    pytest.fail("no hold trial generated")


def test_keyboard_mashing_earns_little_on_creative_task():
    item = items.generate("alt_uses", 5, random.Random(3), {})
    assert items.score_response(item, "aaaa\nbbbb\ncccc\nzzzz", 20000)["y"] == 0.0


# ---- sessions ----------------------------------------------------------------

def _play(db, profile, dimension, mode="assess", user=None, now=None):
    user = user or sim.SimUser({k: 0.5 for k in DIMENSION_KEYS}, seed=1)
    start = engine.start_session(db, profile, dimension, mode, seed=11, now=now)
    trial_id, count = start["trial_id"], 0
    while True:
        item = json.loads(db.execute("SELECT item_json FROM trial WHERE id = ?", (trial_id,)).fetchone()["item_json"])
        response, rt, focus, conf = user.respond(item)
        result = engine.answer(db, start["session_id"], trial_id, response, rt, focus, conf, now=now)
        count += 1
        assert count < 60
        if result["done"]:
            break
        trial_id = result["trial_id"]
    return start["session_id"], engine.finish_session(db, start["session_id"], self_estimate=count // 2, now=now)


@pytest.mark.parametrize("dimension", DIMENSION_KEYS)
def test_every_dimension_runs_end_to_end_in_both_modes(db, profile, dimension):
    for mode in ("assess", "train"):
        _, summary = _play(db, profile, dimension, mode)
        assert summary["stats"]["n"] > 0
    assert any(d["key"] == dimension and d["n_trials"] > 0 for d in twin.profile_view(db, profile))


def test_answer_rejects_duplicates_and_bad_ids(db, profile):
    start = engine.start_session(db, profile, "attention", "assess", seed=2)
    engine.answer(db, start["session_id"], start["trial_id"], "left", 500)
    with pytest.raises(SessionError):
        engine.answer(db, start["session_id"], start["trial_id"], "left", 500)
    with pytest.raises(SessionError):
        engine.answer(db, start["session_id"], 999999, "left", 500)
    with pytest.raises(SessionError):
        engine.answer(db, "nope", 1, "left", 500)


@pytest.mark.parametrize("rt", [None, "fast", -5, float("nan"), float("inf"), 1e12])
def test_bad_response_times_never_crash_or_corrupt(db, profile, rt):
    start = engine.start_session(db, profile, "attention", "assess", seed=2)
    result = engine.answer(db, start["session_id"], start["trial_id"], "left", rt)
    assert np.isfinite(result["live"]["pct"])


@pytest.mark.parametrize(
    "response",
    [None, "", 123, {"a": 1}, ["x"], "x" * 100000, "<script>alert(1)</script>"],
    ids=["none", "empty", "number", "object", "list", "huge", "markup"],
)
def test_malformed_responses_never_crash(db, profile, response):
    for dimension in ("attention", "working_memory", "logical_reasoning", "creative_thinking"):
        start = engine.start_session(db, profile, dimension, "assess", seed=3)
        result = engine.answer(db, start["session_id"], start["trial_id"], response, 1000)
        assert np.isfinite(result["live"]["pct"])


def test_too_fast_answers_are_down_weighted(db, profile):
    start = engine.start_session(db, profile, "logical_reasoning", "assess", seed=4)
    result = engine.answer(db, start["session_id"], start["trial_id"], "1", 50)
    assert "too_fast" in result["flags"] and result["weight"] <= 0.25


def test_focus_loss_is_down_weighted(db, profile):
    start = engine.start_session(db, profile, "attention", "assess", seed=4)
    result = engine.answer(db, start["session_id"], start["trial_id"], "left", 700, focus_lost=True)
    assert "focus_lost" in result["flags"] and result["weight"] <= 0.3


def test_finish_can_be_called_early_and_twice(db, profile):
    start = engine.start_session(db, profile, "attention", "assess", seed=5)
    engine.answer(db, start["session_id"], start["trial_id"], "left", 600)
    first = engine.finish_session(db, start["session_id"])
    second = engine.finish_session(db, start["session_id"])
    assert first["session_id"] == second["session_id"]
    with pytest.raises(SessionError):
        engine.answer(db, start["session_id"], start["trial_id"], "left", 600)


def test_abandoned_session_without_answers_leaves_no_history(db, profile):
    start = engine.start_session(db, profile, "attention", "assess", seed=6)
    engine.finish_session(db, start["session_id"])
    assert twin.history(db, profile) == {}


def test_consent_is_required():
    conn = storage.connect(":memory:")
    for bad in (None, {}, {"store": False}, "yes"):
        with pytest.raises(SessionError):
            engine.create_profile(conn, bad)


# ---- twin --------------------------------------------------------------------

def test_history_is_kept_for_every_session(db, profile):
    _play(db, profile, "attention")
    _play(db, profile, "attention", "train")
    assert len(twin.history(db, profile)["attention"]) == 2


def test_uncertainty_grows_with_time_since_last_evidence(db, profile):
    from datetime import timedelta
    now = storage.utcnow()
    _play(db, profile, "attention", now=now)
    soon = next(d for d in twin.profile_view(db, profile, now) if d["key"] == "attention")
    later = next(d for d in twin.profile_view(db, profile, now + timedelta(days=60)) if d["key"] == "attention")
    assert later["width"] > soon["width"]


def test_projection_refuses_when_history_is_short():
    points = [dict(at="2026-10-01T00:00:00+00:00", theta=0.1, theta_sd=0.5, pct=50, low=30, high=70)] * 2
    assert not twin.project(points, storage.parse_iso("2026-10-10T00:00:00+00:00"))["available"]


def test_projection_gives_ranges_that_widen_with_horizon():
    points = [
        dict(at=f"2026-10-{d:02d}T00:00:00+00:00", theta=0.1 + 0.02 * d, theta_sd=0.4, pct=50 + d, low=30, high=70)
        for d in (1, 5, 9, 14, 20)
    ]
    result = twin.project(points, storage.parse_iso("2026-10-21T00:00:00+00:00"))
    assert result["available"]
    widths = [r["high90"] - r["low90"] for r in result["ranges"]]
    assert widths[0] < widths[-1] and widths[0] > 5
    assert "not a prediction" in result["wording"]


def test_goal_probability_tracks_evidence(db, profile):
    twin.add_goal(db, profile, "attention", 30, "2030-01-01T00:00:00+00:00")
    strong = sim.SimUser({k: 2.0 for k in DIMENSION_KEYS}, seed=3)
    before = twin.goals_view(db, profile)[0]["prob_reached"]
    _play(db, profile, "attention", user=strong)
    assert twin.goals_view(db, profile)[0]["prob_reached"] > before


def test_goal_validation(db, profile):
    for dim, target, due in (("nope", 50, "2030-01-01"), ("attention", 200, "2030-01-01"), ("attention", "x", "2030-01-01"), ("attention", 50, "soon")):
        with pytest.raises(SessionError):
            twin.add_goal(db, profile, dim, target, due)


# ---- planner -----------------------------------------------------------------

def test_new_profile_plan_prioritises_unknowns_and_explains_every_session(db, profile):
    plan = planner.refresh_plan(db, profile)
    assert len(plan["days"]) == 7
    for day in plan["days"]:
        assert len({s["dimension"] for s in day["sessions"]}) == len(day["sessions"])
        for s in day["sessions"]:
            assert s["why"] and s["success_measure"]
            assert s["mode"] == "assess"


def test_goal_lifts_that_dimension_in_the_plan(db, profile):
    for dim in DIMENSION_KEYS:
        _play(db, profile, dim)
    base = {r["dimension"]: r["priority"] for r in planner.build_plan(db, profile)["ranked"]}
    twin.add_goal(db, profile, "spatial_reasoning", 95, "2030-01-01T00:00:00+00:00")
    boosted = {r["dimension"]: r["priority"] for r in planner.build_plan(db, profile)["ranked"]}
    assert boosted["spatial_reasoning"] > base["spatial_reasoning"]


def test_plan_versions_record_changes(db, profile):
    planner.refresh_plan(db, profile)
    _play(db, profile, "attention")
    second = planner.refresh_plan(db, profile)
    assert second["version"] == 2 and second["changes"]


def test_priority_weights_sum_to_one():
    assert abs(sum(planner.WEIGHTS.values()) - 1.0) < 1e-9


# ---- privacy -----------------------------------------------------------------

def test_delete_removes_every_row(db, profile):
    _play(db, profile, "attention")
    planner.refresh_plan(db, profile)
    assert storage.delete_profile(db, profile)
    for table in storage.PROFILE_TABLES:
        assert db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE profile_id = ?", (profile,)).fetchone()["c"] == 0
    assert db.execute("SELECT COUNT(*) AS c FROM profile").fetchone()["c"] == 0


def test_retention_purges_only_expired_profiles(db):
    from datetime import timedelta
    now = storage.utcnow()
    old = engine.create_profile(db, dict(store=True), retention_days=7, now=now - timedelta(days=30))
    fresh = engine.create_profile(db, dict(store=True), retention_days=7, now=now)
    assert storage.purge_expired(db, now) == 1
    ids = {r["id"] for r in db.execute("SELECT id FROM profile").fetchall()}
    assert ids == {fresh} and old not in ids


def test_export_contains_trials_and_no_grid(db, profile):
    _play(db, profile, "attention")
    data = storage.export_profile(db, profile)
    assert data["trial"] and all("grid_json" not in r for r in data["dim_state"])
    json.dumps(data)
