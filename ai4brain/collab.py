"""AI Collaboration Score: how effectively a person works with an AI, on a 0-100 scale.

The score is measured from behaviour in scripted rounds, in which a simulated assistant
gives reasoning that is sometimes deliberately flawed. Because the flaws are planted,
catching them is an observed signal rather than a self-report.

    Score = 100 * (0.20 C + 0.25 V + 0.20 I + 0.20 A + 0.15 R)

C clarification, V critical verification, I iteration, A autonomy, R responsible use.
Each component is a share of successes with Beta(1, 1) smoothing, and V is hit rate minus
false-alarm rate. The weights are the brief's design proposal: they are not validated, so
the app also reports how much the score moves when weights are perturbed.
"""

import json

import numpy as np

from . import guard
from .storage import dumps, iso, utcnow

WEIGHTS = dict(clarification=0.20, verification=0.25, iteration=0.20, autonomy=0.20, responsible=0.15)
NAMES = dict(
    clarification="Clarification", verification="Critical verification", iteration="Iteration",
    autonomy="Autonomy", responsible="Responsible use",
)
COMPONENT_TIPS = dict(
    clarification="When a request is vague, try asking one specific question before accepting an answer.",
    verification="Try checking each reasoning step against the facts you were given, especially the last step.",
    iteration="When an answer looks off, try telling the AI what is wrong and asking for another pass.",
    autonomy="Try committing to your own first answer before you look at what the AI suggests.",
    responsible="Before sharing an AI output, think about whose data is in it and who is accountable for the decision.",
)

SCENARIOS = [
    dict(
        id="trip_budget", title="Trip budget",
        prompt="A 3-day trip costs 120 per day for the hotel, 45 per day for food, and 90 for transport in total. What does the trip cost overall?",
        ambiguous=False, options=["585", "765", "495", "675"], correct="585",
        draft=dict(
            steps=[
                dict(text="Hotel: 3 x 120 = 360.", flawed=False),
                dict(text="Food: 3 x 45 = 135.", flawed=False),
                dict(text="Transport: 3 x 90 = 270.", flawed=True,
                     why="Transport is 90 in total, not per day."),
                dict(text="Overall: 360 + 135 + 270 = 765.", flawed=True,
                     why="This total carries over the transport error."),
            ],
            conclusion="765",
        ),
        refined=dict(note="You're right to push back. Transport was a single cost.",
                     steps=["Hotel 360 + food 135 + transport 90 = 585."], conclusion="585"),
    ),
    dict(
        id="sales_figure", title="Sales figure",
        prompt="Your manager asks for 'the sales figure for last quarter'. The sheet shows gross sales of 48,000 and net sales of 41,000 for that quarter. Which number should you send?",
        ambiguous=True, options=["48,000", "41,000", "89,000", "7,000"], correct="41,000",
        clarifications=[
            dict(q="Does your manager want gross or net sales?", relevant=True, a="Net sales. Finance reports everything net."),
            dict(q="Which spreadsheet program should I use?", relevant=False, a="Any program is fine."),
            dict(q="Should the number be in bold?", relevant=False, a="That doesn't matter."),
        ],
        draft=dict(
            steps=[
                dict(text="Last quarter's row is the right row to read.", flawed=False),
                dict(text="'Sales figure' means gross sales.", flawed=True,
                     why="This is an assumption. The request doesn't say gross or net."),
                dict(text="So the number to send is 48,000.", flawed=True,
                     why="It depends on the unverified assumption before it."),
            ],
            conclusion="48,000",
        ),
        refined=dict(note="I assumed gross. If your manager reports net sales, the figure changes.",
                     steps=["With net sales, the figure is 41,000."], conclusion="41,000"),
    ),
    dict(
        id="shop_discount", title="Discount and tax",
        prompt="An item costs 50. A shop takes 20% off, then adds 10% tax on the discounted price. What do you pay?",
        ambiguous=False, options=["44", "45", "40", "49.50"], correct="44",
        draft=dict(
            steps=[
                dict(text="20% off 50 leaves 40.", flawed=False),
                dict(text="10% tax on 40 is 4.", flawed=False),
                dict(text="So you pay 40 + 4 = 44.", flawed=False),
            ],
            conclusion="44",
        ),
        refined=dict(note="I rechecked each step and it still holds.", steps=["40 + 4 = 44."], conclusion="44"),
    ),
    dict(
        id="study_claim", title="Practice claim",
        prompt="You are writing a short note on whether daily practice helps learning. The AI wrote a sentence for you. What should you do with it?",
        ambiguous=False,
        options=[
            "Paste it in as written",
            "Find and read the source first, and soften the claim",
            "Delete the citation but keep the claim as written",
            "Add more citations from the AI without checking them",
        ],
        correct="Find and read the source first, and soften the claim",
        draft=dict(
            steps=[
                dict(text="Spaced practice is widely studied in learning research.", flawed=False),
                dict(text="Smith and Lee (2021) proved daily practice works for everyone.", flawed=True,
                     why="The AI cannot confirm this source exists, and 'proved' and 'everyone' overstate any single study."),
                dict(text="So the note can state this as settled fact.", flawed=True,
                     why="The conclusion rests on an unverified, overstated claim."),
            ],
            conclusion="Paste it in as written",
        ),
        refined=dict(note="I can't verify that citation, so please check it. A safer wording is 'research suggests spaced practice often helps'.",
                     steps=["Keep the claim modest, and cite only sources you've read."],
                     conclusion="Find and read the source first, and soften the claim"),
    ),
    dict(
        id="room_booking", title="Workshop room",
        prompt="You need a room for a 2-hour workshop for 'about 30 people'. Room A seats 25. Room B seats 40 but is free for only 90 minutes. What should you do?",
        ambiguous=True,
        options=["Book Room A", "Book Room B", "Find another room or split the session", "Cancel the workshop"],
        correct="Find another room or split the session",
        clarifications=[
            dict(q="How many people have actually signed up?", relevant=True, a="28 people have signed up."),
            dict(q="Can the workshop be shorter than 2 hours?", relevant=True, a="No, 2 hours is firm."),
            dict(q="What colour are the chairs?", relevant=False, a="Grey, though it doesn't matter."),
        ],
        draft=dict(
            steps=[
                dict(text="Room A is too small for about 30 people.", flawed=False),
                dict(text="Room B has enough seats.", flawed=False),
                dict(text="So Room B works for the workshop.", flawed=True,
                     why="Room B is free for only 90 minutes, and the workshop needs 120."),
            ],
            conclusion="Book Room B",
        ),
        refined=dict(note="I missed the time limit on Room B. Neither room fits as stated.",
                     steps=["Look for another room, or split the group or the session."],
                     conclusion="Find another room or split the session"),
    ),
    dict(
        id="coin_homework", title="Two coins",
        prompt="You flip two fair coins. What is the chance of at least one heads?",
        ambiguous=False, options=["3/4", "1/2", "1/4", "2/3"], correct="3/4",
        draft=dict(
            steps=[
                dict(text="There are four equally likely outcomes: HH, HT, TH, TT.", flawed=False),
                dict(text="Only TT has no heads.", flawed=False),
                dict(text="So the chance of at least one heads is 3 out of 4.", flawed=False),
            ],
            conclusion="3/4",
        ),
        refined=dict(note="I rechecked this and the count holds.", steps=["3 of 4 outcomes contain heads."], conclusion="3/4"),
        responsible=dict(
            q="This is for graded homework, and the course rules say no AI help. What do you do?",
            options=[
                dict(text="Submit the AI's working as my own", ok=False),
                dict(text="Work it out myself, or ask the teacher what is allowed", ok=True),
                dict(text="Reword it so nobody can tell", ok=False),
            ],
        ),
    ),
    dict(
        id="hiring_rank", title="Ranking candidates",
        prompt="You have three job applications with names, birth dates and home addresses. You ask the AI to rank them. What is the best next step?",
        ambiguous=False,
        options=[
            "Send the AI's ranking to HR as the decision",
            "Remove personal details, use the ranking as one input, and let people decide",
            "Hire the person the AI ranked first",
            "Ask the AI to find more about them online",
        ],
        correct="Remove personal details, use the ranking as one input, and let people decide",
        draft=dict(
            steps=[
                dict(text="Relevant experience is a fair thing to compare.", flawed=False),
                dict(text="Older candidates adapt less well, so they should rank lower.", flawed=True,
                     why="This is an unfair stereotype about age, not evidence about the candidates."),
                dict(text="So the AI's ranking can stand as the decision.", flawed=True,
                     why="A hiring decision needs human accountability and a fair basis."),
            ],
            conclusion="Send the AI's ranking to HR as the decision",
        ),
        refined=dict(note="Age shouldn't have been a factor. I'll compare experience only, and people should make the decision.",
                     steps=["Remove personal details and compare skills against the job's needs."],
                     conclusion="Remove personal details, use the ranking as one input, and let people decide"),
        responsible=dict(
            q="Before pasting the applications into an AI tool, what do you do?",
            options=[
                dict(text="Paste everything; the tool needs full context", ok=False),
                dict(text="Remove names, birth dates and addresses, and check what the organisation allows", ok=True),
                dict(text="Paste them, then delete the chat afterwards", ok=False),
            ],
        ),
    ),
    dict(
        id="small_sample", title="Comparing two methods",
        prompt="Group A (10 people) improved 20% using method A. Group B (200 people) improved 15% using method B. What is a fair conclusion?",
        ambiguous=False,
        options=[
            "Method A is clearly better",
            "Method B is clearly better",
            "There isn't enough evidence to pick a clear winner",
            "Neither method works",
        ],
        correct="There isn't enough evidence to pick a clear winner",
        draft=dict(
            steps=[
                dict(text="Group A's improvement figure is higher than Group B's.", flawed=False),
                dict(text="A 5-point gap proves method A is better.", flawed=True,
                     why="Group A has only 10 people, so a 5-point gap could easily be chance."),
                dict(text="So method A should replace method B.", flawed=True,
                     why="The recommendation rests on the unsupported step above."),
            ],
            conclusion="Method A is clearly better",
        ),
        refined=dict(note="I overlooked the group sizes. Ten people can't settle this.",
                     steps=["Collect more data before picking a method."],
                     conclusion="There isn't enough evidence to pick a clear winner"),
        responsible=dict(
            q="Your manager wants one line for a report. What do you write?",
            options=[
                dict(text="'AI analysis proves method A works best'", ok=False),
                dict(text="'Early data is inconclusive; group A is small. AI helped draft this.'", ok=True),
                dict(text="'Method A is better' with no mention of the sample size", ok=False),
            ],
        ),
    ),
]
SCENARIO_BY_ID = {s["id"]: s for s in SCENARIOS}


def client_scenario(scenario):
    """Remove answers and flaw markers before sending a scenario to the browser."""
    return dict(
        id=scenario["id"], title=scenario["title"], prompt=scenario["prompt"], ambiguous_hint=False,
        options=scenario["options"],
        clarifications=[c["q"] for c in scenario.get("clarifications", [])] or [
            "Is any information missing from this problem?",
            "What assumptions did you make?",
        ],
        draft=dict(steps=[s["text"] for s in scenario["draft"]["steps"]], conclusion=scenario["draft"]["conclusion"]),
        responsible=dict(
            q=scenario["responsible"]["q"],
            options=[o["text"] for o in scenario["responsible"]["options"]],
        ) if scenario.get("responsible") else None,
    )


def clarification_answer(scenario, index, free_text=None):
    """Answer a clarifying question. Free text gets a best-effort reply."""
    known = scenario.get("clarifications", [])
    if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(known):
        return known[index]["a"]
    if not known:
        return "This problem gives everything you need, so nothing is missing."
    relevant = next((c for c in known if c["relevant"]), None)
    return relevant["a"] if relevant else "I don't have more on that."


def next_scenario(db, profile_id):
    played = {r["scenario_id"] for r in db.execute(
        "SELECT scenario_id FROM collab_round WHERE profile_id = ?", (profile_id,)).fetchall()}
    remaining = [s for s in SCENARIOS if s["id"] not in played]
    return dict(
        scenario=client_scenario(remaining[0]) if remaining else None,
        played=len(played), total=len(SCENARIOS),
    )


def _as_list(value):
    return value if isinstance(value, list) else []


def _as_count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def evaluate_round(scenario, events):
    """Turn a round's events into counts for each score component and a debrief."""
    flagged = {i for i in _as_list(events.get("flagged_steps")) if isinstance(i, int) and not isinstance(i, bool)}
    steps = scenario["draft"]["steps"]
    flawed = [i for i, s in enumerate(steps) if s["flawed"]]
    valid = [i for i, s in enumerate(steps) if not s["flawed"]]
    hits = len([i for i in flawed if i in flagged])
    false_alarms = len([i for i in valid if i in flagged])

    final = events.get("final_answer")
    final_correct = final == scenario["correct"]
    draft_wrong = scenario["draft"]["conclusion"] != scenario["correct"]
    refine_count = _as_count(events.get("refine_count"))
    own = events.get("own_answer")

    clar_idx = _as_list(events.get("clarifications"))
    known = scenario.get("clarifications", [])
    asked_relevant = any(isinstance(i, int) and 0 <= i < len(known) and known[i]["relevant"] for i in clar_idx)
    free_clar = [t for t in _as_list(events.get("free_questions")) if isinstance(t, str) and t.strip()]
    if scenario["ambiguous"] and free_clar:
        asked_relevant = True

    counts = dict(
        clar_n=1 if scenario["ambiguous"] else 0,
        clar_s=1 if scenario["ambiguous"] and asked_relevant else 0,
        hit_n=len(flawed), hit_s=hits, fa_n=len(valid), fa_s=false_alarms,
        own_n=1, own_s=1 if own else 0,
        rely_n=1, rely_s=1 if final_correct else 0,
    )
    # Iteration counts on rounds where a first draft wasn't enough. Someone who fixes it
    # unaided hasn't failed to iterate, so that round is left out.
    if draft_wrong and not (final_correct and refine_count == 0):
        counts["iter_n"] = 1
        counts["iter_s"] = 1 if (final_correct and 1 <= refine_count <= 2) else 0
    else:
        counts["iter_n"] = counts["iter_s"] = 0

    responsible_ok = None
    if scenario.get("responsible"):
        pick = events.get("responsible_choice")
        ok_text = next(o["text"] for o in scenario["responsible"]["options"] if o["ok"])
        responsible_ok = pick == ok_text
        counts["resp_n"], counts["resp_s"] = 1, 1 if responsible_ok else 0
    else:
        counts["resp_n"] = counts["resp_s"] = 0
    typed = " ".join(free_clar)
    pii = guard.find_personal_data(typed)
    if pii:
        counts["resp_n"] += 1

    debrief = dict(
        final_correct=final_correct, correct=scenario["correct"], draft_wrong=draft_wrong,
        steps=[dict(text=s["text"], flawed=s["flawed"], why=s.get("why"), flagged=i in flagged)
               for i, s in enumerate(steps)],
        hits=hits, missed=len(flawed) - hits, false_alarms=false_alarms,
        asked_relevant=asked_relevant, ambiguous=scenario["ambiguous"],
        responsible_ok=responsible_ok, personal_data=pii,
    )
    return counts, debrief


def record_round(db, profile_id, scenario_id, events, now=None):
    now = now or utcnow()
    scenario = SCENARIO_BY_ID.get(scenario_id)
    if scenario is None:
        raise ValueError("Unknown scenario")
    if not isinstance(events, dict):
        raise ValueError("Events must be an object")
    counts, debrief = evaluate_round(scenario, events)
    safe_events = dict(events)
    safe_events["free_questions"] = [guard.redact_personal_data(t) for t in _as_list(events.get("free_questions")) if isinstance(t, str)]
    db.execute("DELETE FROM collab_round WHERE profile_id = ? AND scenario_id = ?", (profile_id, scenario_id))
    db.execute(
        "INSERT INTO collab_round (profile_id, scenario_id, events_json, result_json, at) VALUES (?,?,?,?,?)",
        (profile_id, scenario_id, dumps(safe_events), dumps(dict(counts=counts, debrief=debrief)), iso(now)),
    )
    db.commit()
    return debrief


def score_counts(total, seed=7, draws=4000):
    """Compute the score, its credible interval, and sensitivity to the weights."""
    rng = np.random.default_rng(seed)

    def beta(s, n):
        return rng.beta(s + 1, n - s + 1, draws)

    def smooth(s, n):
        return (s + 1) / (n + 2)

    h, f = total["hit_s"], total["fa_s"]
    point = dict(
        clarification=smooth(total["clar_s"], total["clar_n"]),
        verification=max(0.0, smooth(h, total["hit_n"]) - smooth(f, total["fa_n"])),
        iteration=smooth(total["iter_s"], total["iter_n"]),
        autonomy=0.5 * smooth(total["own_s"], total["own_n"]) + 0.5 * smooth(total["rely_s"], total["rely_n"]),
        responsible=smooth(total["resp_s"], total["resp_n"]),
    )
    samples = dict(
        clarification=beta(total["clar_s"], total["clar_n"]),
        verification=np.clip(beta(h, total["hit_n"]) - beta(f, total["fa_n"]), 0.0, 1.0),
        iteration=beta(total["iter_s"], total["iter_n"]),
        autonomy=0.5 * beta(total["own_s"], total["own_n"]) + 0.5 * beta(total["rely_s"], total["rely_n"]),
        responsible=beta(total["resp_s"], total["resp_n"]),
    )
    keys = list(WEIGHTS)
    w = np.array([WEIGHTS[k] for k in keys])
    point_vec = np.array([point[k] for k in keys])
    score = float(100.0 * (w * point_vec).sum())
    matrix = np.stack([samples[k] for k in keys], axis=1)
    sampled = 100.0 * (matrix * w).sum(axis=1)
    # Weight sensitivity: redraw the weights around the proposal and hold evidence fixed.
    weight_draws = rng.dirichlet(w * 40.0, draws)
    sensitivity = 100.0 * (weight_draws * point_vec).sum(axis=1)
    return dict(
        score=round(score, 1),
        low=round(float(np.percentile(sampled, 5)), 1),
        high=round(float(np.percentile(sampled, 95)), 1),
        weight_low=round(float(np.percentile(sensitivity, 5)), 1),
        weight_high=round(float(np.percentile(sensitivity, 95)), 1),
        equal_weights_score=round(float(100.0 * point_vec.mean()), 1),
        point={k: round(float(point[k]), 3) for k in keys},
    )


EMPTY_COUNTS = dict(clar_n=0, clar_s=0, hit_n=0, hit_s=0, fa_n=0, fa_s=0, own_n=0, own_s=0,
                    rely_n=0, rely_s=0, iter_n=0, iter_s=0, resp_n=0, resp_s=0)


def score_profile(db, profile_id):
    rows = db.execute(
        "SELECT scenario_id, result_json, at FROM collab_round WHERE profile_id = ? ORDER BY at, id", (profile_id,)
    ).fetchall()
    total = dict(EMPTY_COUNTS)
    timeline = []
    for row in rows:
        counts = json.loads(row["result_json"])["counts"]
        for k in total:
            total[k] += counts.get(k, 0)
        timeline.append(dict(at=row["at"], score=score_counts(total)["score"]))
    result = score_counts(total)
    components = {}
    measured = dict(
        clarification=total["clar_n"], verification=total["hit_n"] + total["fa_n"],
        iteration=total["iter_n"], autonomy=total["own_n"], responsible=total["resp_n"],
    )
    for key in WEIGHTS:
        components[key] = dict(
            name=NAMES[key], weight=WEIGHTS[key], score=result["point"][key], observations=measured[key],
        )
    return dict(
        rounds=len(rows), total_rounds=len(SCENARIOS), score=result["score"], low=result["low"], high=result["high"],
        weight_low=result["weight_low"], weight_high=result["weight_high"],
        equal_weights_score=result["equal_weights_score"], components=components, counts=total, timeline=timeline,
        note="A design proposal, not a validated instrument. Treat it as a mirror for your habits and not as a verdict.",
    )


def simulate_persona_events(scenario, persona, rng):
    """Generate plausible events for a behaviour persona. Used by tests, seeding and evaluation."""
    steps = scenario["draft"]["steps"]
    flawed = [i for i, s in enumerate(steps) if s["flawed"]]
    valid = [i for i, s in enumerate(steps) if not s["flawed"]]
    p = PERSONAS[persona]
    flagged = [i for i in flawed if rng.random() < p["catch"]] + [i for i in valid if rng.random() < p["false_alarm"]]
    events = dict(flagged_steps=flagged, refine_count=0, clarifications=[], free_questions=[])
    if rng.random() < p["own_first"]:
        events["own_answer"] = scenario["correct"] if rng.random() < p["skill"] else scenario["options"][-1]
    known = scenario.get("clarifications", [])
    if known and rng.random() < p["clarify"]:
        events["clarifications"] = [next(i for i, c in enumerate(known) if c["relevant"])]
    draft_wrong = scenario["draft"]["conclusion"] != scenario["correct"]
    noticed = draft_wrong and any(i in flagged for i in flawed)
    if noticed and rng.random() < p["refine"]:
        events["refine_count"] = 1
    if draft_wrong:
        if events["refine_count"] or (noticed and rng.random() < p["skill"]):
            events["final_answer"] = scenario["correct"]
        else:
            events["final_answer"] = scenario["draft"]["conclusion"]
    else:
        events["final_answer"] = scenario["correct"] if rng.random() > p["false_alarm"] else scenario["options"][-1]
    if scenario.get("responsible"):
        options = scenario["responsible"]["options"]
        ok = next(o["text"] for o in options if o["ok"])
        bad = next(o["text"] for o in options if not o["ok"])
        events["responsible_choice"] = ok if rng.random() < p["responsible"] else bad
    return events


PERSONAS = {
    "careful_partner": dict(catch=0.9, false_alarm=0.05, own_first=0.9, clarify=0.9, refine=0.85, skill=0.85, responsible=0.95),
    "average_user": dict(catch=0.5, false_alarm=0.12, own_first=0.4, clarify=0.4, refine=0.6, skill=0.6, responsible=0.7),
    "blind_accepter": dict(catch=0.05, false_alarm=0.02, own_first=0.05, clarify=0.05, refine=0.1, skill=0.4, responsible=0.4),
    "over_sceptic": dict(catch=0.9, false_alarm=0.8, own_first=0.8, clarify=0.3, refine=0.3, skill=0.6, responsible=0.8),
    "full_delegator": dict(catch=0.0, false_alarm=0.0, own_first=0.0, clarify=0.0, refine=0.0, skill=0.2, responsible=0.15),
}
