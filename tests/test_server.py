import pytest

from ai4brain.server import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "t.db"))
    return app.test_client()


@pytest.fixture
def me(client):
    r = client.post("/api/profile", json=dict(consent=dict(store=True)))
    return {"X-Profile": r.get_json()["profile_id"]}


def test_home_and_meta_load(client):
    assert client.get("/").status_code == 200
    meta = client.get("/api/meta").get_json()
    assert len(meta["dimensions"]) == 10


def test_profile_needs_consent(client):
    assert client.post("/api/profile", json=dict(consent=dict(store=False))).status_code == 400
    assert client.post("/api/profile", json={}).status_code == 400


def test_unknown_profile_is_rejected_everywhere(client):
    bad = {"X-Profile": "nope"}
    for path in ("/api/twin", "/api/plan", "/api/coach", "/api/export", "/api/me", "/api/collab/next"):
        assert client.get(path, headers=bad).status_code == 400, path
    assert client.get("/api/twin").status_code == 400


def test_full_session_over_http(client, me):
    start = client.post("/api/session", json=dict(dimension="logical_reasoning", mode="assess"), headers=me).get_json()
    assert "answer" not in start["item"]
    sid, tid = start["session_id"], start["trial_id"]
    for _ in range(30):
        r = client.post(f"/api/session/{sid}/answer", json=dict(trial_id=tid, response="1", rt_ms=2500, confidence=0.7), headers=me).get_json()
        assert "answer" not in (r["item"] or {})
        if r["done"]:
            break
        tid = r["trial_id"]
    done = client.post(f"/api/session/{sid}/finish", json=dict(self_estimate=3), headers=me).get_json()
    assert done["summary"]["stats"]["n"] > 0 and done["plan_changes"]
    twin = client.get("/api/twin", headers=me).get_json()
    assert twin["history"]["logical_reasoning"]
    assert client.get("/api/twin/logical_reasoning", headers=me).get_json()["moved"]


def test_one_profile_cannot_touch_another_session(client, me):
    other = {"X-Profile": client.post("/api/profile", json=dict(consent=dict(store=True))).get_json()["profile_id"]}
    start = client.post("/api/session", json=dict(dimension="attention"), headers=me).get_json()
    r = client.post(f"/api/session/{start['session_id']}/answer", json=dict(trial_id=start["trial_id"], response="left"), headers=other)
    assert r.status_code == 400
    assert client.post(f"/api/session/{start['session_id']}/finish", json={}, headers=other).status_code == 400


def test_one_profile_cannot_delete_another_goal(client, me):
    other = {"X-Profile": client.post("/api/profile", json=dict(consent=dict(store=True))).get_json()["profile_id"]}
    gid = client.post("/api/goals", json=dict(dimension="attention", target_pct=70, due_date="2030-01-01T00:00:00+00:00"), headers=me).get_json()["id"]
    client.delete(f"/api/goals/{gid}", headers=other)
    assert client.get("/api/twin", headers=me).get_json()["goals"]


@pytest.mark.parametrize("trial_id", [None, "x", {"a": 1}, [1], 99999, 1.5, True])
def test_bad_trial_ids_return_400(client, me, trial_id):
    start = client.post("/api/session", json=dict(dimension="attention"), headers=me).get_json()
    r = client.post(f"/api/session/{start['session_id']}/answer", json=dict(trial_id=trial_id, response="left"), headers=me)
    assert r.status_code == 400


@pytest.mark.parametrize("body", [
    dict(dimension="nope"), dict(dimension=None), dict(dimension=["attention"]), dict(dimension="attention", mode="x"),
])
def test_bad_session_requests_return_400(client, me, body):
    assert client.post("/api/session", json=body, headers=me).status_code == 400


def test_unknown_mood_is_ignored(client, me):
    assert client.post("/api/session", json=dict(dimension="attention", mood="<b>sad</b>"), headers=me).status_code == 200


def test_non_json_bodies_do_not_crash(client, me):
    for path in ("/api/session", "/api/coach", "/api/goals", "/api/collab/round", "/api/consent", "/api/delete"):
        r = client.post(path, data="not json", content_type="application/json", headers=me)
        assert r.status_code < 500, path


@pytest.mark.parametrize("events", [
    "text", 7, [1], dict(flagged_steps="abc"), dict(flagged_steps=[1e400, "x", None]), dict(clarifications=7),
    dict(free_questions=7), dict(refine_count="many"), dict(refine_count=None), dict(final_answer=["x"]),
])
def test_malformed_collab_events_do_not_crash(client, me, events):
    r = client.post("/api/collab/round", json=dict(scenario_id="trip_budget", events=events), headers=me)
    assert r.status_code < 500


@pytest.mark.parametrize("index", ["x", None, -1, 99, [1], 1.5])
def test_malformed_clarify_does_not_crash(client, me, index):
    r = client.post("/api/collab/clarify", json=dict(scenario_id="sales_figure", index=index), headers=me)
    assert r.status_code == 200 and r.get_json()["answer"]


@pytest.mark.parametrize("patch", [dict(retention_days="x"), dict(retention_days=None), dict(retention_days=[1])])
def test_bad_retention_does_not_crash(client, me, patch):
    assert client.post("/api/consent", json=patch, headers=me).status_code == 400


def test_coach_over_http(client, me):
    r = client.post("/api/coach", json=dict(text="Do I have dementia?"), headers=me).get_json()
    assert r["source"] == "safety response"
    assert client.get("/api/coach", headers=me).get_json()["messages"]


def test_oversized_request_is_refused(client, me):
    r = client.post("/api/coach", json=dict(text="x" * 400000), headers=me)
    assert r.status_code == 413


def test_export_and_delete(client, me):
    client.post("/api/session", json=dict(dimension="attention"), headers=me)
    assert client.get("/api/export", headers=me).get_json()["profile"]
    assert client.post("/api/delete", json={}, headers=me).status_code == 400
    assert client.post("/api/delete", json=dict(confirm="delete"), headers=me).get_json()["deleted"]
    assert client.get("/api/me", headers=me).status_code == 400


def test_demo_profile_is_labelled_and_never_sent_to_a_model(client):
    pid = client.post("/api/demo").get_json()["profile_id"]
    me = client.get("/api/me", headers={"X-Profile": pid}).get_json()
    assert me["is_demo"] and me["consent"]["llm"] is False
