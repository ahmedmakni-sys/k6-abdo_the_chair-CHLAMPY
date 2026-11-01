"""HTTP API and static host for the web app."""

import json
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory

from . import __version__, coach, collab, demo, engine, planner, storage, twin
from .dimensions import DIMENSION_KEYS, DIMENSIONS
from .engine import SessionError
from .items import INSTRUCTIONS

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def create_app(db_path=None):
    app = Flask(__name__, static_folder=None)
    app.config["DB_PATH"] = db_path
    app.config["MAX_CONTENT_LENGTH"] = 256 * 1024
    app.json.sort_keys = False
    # Remove anything past its retention period each time the server starts.
    boot_db = storage.connect(db_path)
    storage.purge_expired(boot_db)
    boot_db.close()

    def db():
        if "db" not in g:
            g.db = storage.connect(app.config["DB_PATH"])
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    def body():
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    def profile_id():
        pid = request.headers.get("X-Profile", "")
        if not pid or db().execute("SELECT 1 FROM profile WHERE id = ?", (pid,)).fetchone() is None:
            raise SessionError("Unknown profile. Start again from the welcome page.")
        return pid

    def session_owned(session_id, pid):
        row = db().execute("SELECT profile_id FROM session WHERE id = ?", (session_id,)).fetchone()
        if row is None or row["profile_id"] != pid:
            raise SessionError("Unknown session")

    @app.errorhandler(SessionError)
    def on_session_error(err):
        return jsonify(error=str(err)), 400

    @app.errorhandler(ValueError)
    def on_value_error(err):
        return jsonify(error=str(err)), 400

    @app.errorhandler(404)
    def on_404(_err):
        if request.path.startswith("/api/"):
            return jsonify(error="No such endpoint"), 404
        return send_from_directory(WEB_DIR, "index.html")

    @app.errorhandler(413)
    def on_413(_err):
        return jsonify(error="Request too large"), 413

    # ---- static ----------------------------------------------------------------

    @app.get("/")
    def index():
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/web/<path:name>")
    def web(name):
        return send_from_directory(WEB_DIR, name)

    # ---- meta and profile ------------------------------------------------------

    @app.get("/api/meta")
    def meta():
        return jsonify(
            version=__version__,
            dimensions=[dict(key=k, **DIMENSIONS[k]) for k in DIMENSION_KEYS],
            instructions=INSTRUCTIONS,
            llm_configured=coach.llm_available(),
        )

    @app.post("/api/profile")
    def create_profile():
        data = body()
        pid = engine.create_profile(db(), data.get("consent"), data.get("retention_days", 180))
        return jsonify(profile_id=pid)

    @app.post("/api/demo")
    def create_demo():
        pid = demo.build_demo_profile(db())
        return jsonify(profile_id=pid)

    @app.get("/api/me")
    def me():
        pid = profile_id()
        row = db().execute("SELECT * FROM profile WHERE id = ?", (pid,)).fetchone()
        return jsonify(
            id=pid, created_at=row["created_at"], consent=json.loads(row["consent_json"]),
            retention_days=row["retention_days"], is_demo=bool(row["is_demo"]),
            last_active_at=row["last_active_at"],
        )

    @app.post("/api/consent")
    def update_consent():
        pid = profile_id()
        data = body()
        row = db().execute("SELECT consent_json FROM profile WHERE id = ?", (pid,)).fetchone()
        consent = json.loads(row["consent_json"])
        for key in ("llm", "voice"):
            if key in data:
                consent[key] = bool(data[key])
        if "retention_days" in data:
            value = data["retention_days"]
            if not isinstance(value, int) or isinstance(value, bool):
                raise SessionError("Retention must be a whole number of days")
            days = max(7, min(730, value))
            db().execute("UPDATE profile SET retention_days = ? WHERE id = ?", (days, pid))
        db().execute("UPDATE profile SET consent_json = ? WHERE id = ?", (storage.dumps(consent), pid))
        db().commit()
        return jsonify(ok=True, consent=consent)

    @app.get("/api/export")
    def export():
        return jsonify(storage.export_profile(db(), profile_id()))

    @app.post("/api/delete")
    def delete():
        pid = profile_id()
        if body().get("confirm") != "delete":
            raise SessionError("Deletion needs confirmation")
        storage.delete_profile(db(), pid)
        return jsonify(deleted=True)

    # ---- twin ------------------------------------------------------------------

    @app.get("/api/twin")
    def get_twin():
        pid = profile_id()
        conn = db()
        now = storage.utcnow()
        engine.close_open_sessions(conn, pid, now)
        hist = twin.history(conn, pid)
        view = twin.profile_view(conn, pid, now)
        projections = {d: twin.project(hist.get(d, []), now) for d in DIMENSION_KEYS}
        plan = planner.latest_plan(conn, pid) or planner.refresh_plan(conn, pid, now)
        recent = twin.recent_session_stats(conn, pid, limit=5)
        return jsonify(
            now=storage.iso(now), profile=view, history=hist, projections=projections,
            heatmaps=twin.heatmaps(conn, pid, now), goals=twin.goals_view(conn, pid, now),
            plan=plan, insights=coach.detect_insights(conn, pid, now),
            collab=collab.score_profile(conn, pid),
            state_proxy=recent[0]["state_proxy"] if recent else None,
        )

    @app.get("/api/twin/<dimension>")
    def twin_dimension(dimension):
        pid = profile_id()
        if dimension not in DIMENSIONS:
            raise SessionError("Unknown dimension")
        conn = db()
        trials = engine.dimension_trials(conn, pid, dimension)
        moved = sorted(
            [t for t in trials if t.get("pct_before") is not None],
            key=lambda t: -abs(t["pct_after"] - t["pct_before"]),
        )[:8]
        hist = twin.history(conn, pid).get(dimension, [])
        return jsonify(
            info=dict(key=dimension, **DIMENSIONS[dimension]),
            state=next(d for d in twin.profile_view(conn, pid) if d["key"] == dimension),
            history=hist,
            projection=twin.project(hist, storage.utcnow()),
            moved=[dict(task=t["task"], level=t["level"], correct=t["correct"], rt_ms=t["rt_ms"], weight=t["w"],
                        moved=round(t["pct_after"] - t["pct_before"], 1), flags=t["flags"], at=t["answered_at"])
                   for t in moved],
            trials=len(trials),
        )

    # ---- sessions --------------------------------------------------------------

    @app.post("/api/session")
    def start_session():
        pid = profile_id()
        data = body()
        return jsonify(engine.start_session(
            db(), pid, data.get("dimension"), data.get("mode", "assess"), mood=data.get("mood"),
        ))

    @app.post("/api/session/<session_id>/answer")
    def answer(session_id):
        pid = profile_id()
        session_owned(session_id, pid)
        data = body()
        return jsonify(engine.answer(
            db(), session_id, data.get("trial_id"), data.get("response"), data.get("rt_ms"),
            data.get("focus_lost", False), data.get("confidence"),
        ))

    @app.post("/api/session/<session_id>/finish")
    def finish(session_id):
        pid = profile_id()
        session_owned(session_id, pid)
        data = body()
        summary = engine.finish_session(db(), session_id, data.get("self_estimate"))
        plan = planner.refresh_plan(db(), pid)
        return jsonify(summary=summary, plan_changes=plan.get("changes", []), insights=coach.detect_insights(db(), pid))

    # ---- goals and plan --------------------------------------------------------

    @app.post("/api/goals")
    def add_goal():
        pid = profile_id()
        data = body()
        goal_id = twin.add_goal(db(), pid, data.get("dimension"), data.get("target_pct"), data.get("due_date"))
        planner.refresh_plan(db(), pid)
        return jsonify(id=goal_id)

    @app.delete("/api/goals/<int:goal_id>")
    def delete_goal(goal_id):
        pid = profile_id()
        db().execute("DELETE FROM goal WHERE id = ? AND profile_id = ?", (goal_id, pid))
        db().commit()
        planner.refresh_plan(db(), pid)
        return jsonify(ok=True)

    @app.get("/api/plan")
    def get_plan():
        pid = profile_id()
        plan = planner.latest_plan(db(), pid) or planner.refresh_plan(db(), pid)
        return jsonify(plan=plan, history=planner.plan_history(db(), pid))

    # ---- coach -----------------------------------------------------------------

    @app.post("/api/coach")
    def coach_message():
        pid = profile_id()
        return jsonify(coach.respond(db(), pid, str(body().get("text", ""))))

    @app.get("/api/coach")
    def coach_history():
        return jsonify(messages=coach.conversation(db(), profile_id()))

    # ---- AI collaboration ------------------------------------------------------

    @app.get("/api/collab/next")
    def collab_next():
        pid = profile_id()
        return jsonify(**collab.next_scenario(db(), pid), score=collab.score_profile(db(), pid))

    @app.post("/api/collab/clarify")
    def collab_clarify():
        profile_id()
        data = body()
        scenario = collab.SCENARIO_BY_ID.get(data.get("scenario_id"))
        if scenario is None:
            raise SessionError("Unknown scenario")
        return jsonify(answer=collab.clarification_answer(scenario, data.get("index")))

    @app.post("/api/collab/refine")
    def collab_refine():
        profile_id()
        scenario = collab.SCENARIO_BY_ID.get(body().get("scenario_id"))
        if scenario is None:
            raise SessionError("Unknown scenario")
        return jsonify(scenario["refined"])

    @app.post("/api/collab/round")
    def collab_round():
        pid = profile_id()
        data = body()
        debrief = collab.record_round(db(), pid, data.get("scenario_id"), data.get("events") or {})
        return jsonify(debrief=debrief, score=collab.score_profile(db(), pid))

    @app.post("/api/collab/reset")
    def collab_reset():
        pid = profile_id()
        db().execute("DELETE FROM collab_round WHERE profile_id = ?", (pid,))
        db().commit()
        return jsonify(ok=True)

    return app
