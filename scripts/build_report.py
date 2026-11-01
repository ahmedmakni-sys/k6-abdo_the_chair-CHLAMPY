"""Build the technical report PDF (limit: 8 pages). All results are read from docs/evaluation_results.json."""

import json
import sys
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai4brain.dimensions import DIMENSIONS  # noqa: E402

OUT = ROOT / "deliverables" / "AI4Brain_technical_report.pdf"
R = json.loads((ROOT / "docs" / "evaluation_results.json").read_text(encoding="utf-8"))
FIG = ROOT / "docs" / "figures"
SHOTS = ROOT / "docs" / "screenshots"

INK = colors.HexColor("#0b2239")
INK2 = colors.HexColor("#3f5870")
SIGNAL = colors.HexColor("#1468b8")
LINE = colors.HexColor("#c9d6e2")
ICE = colors.HexColor("#eef4f9")

body = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=13.8, textColor=INK, spaceAfter=4.5, alignment=TA_LEFT)
small = ParagraphStyle("small", parent=body, fontSize=8.4, leading=10.8, textColor=INK2, spaceAfter=3)
cell = ParagraphStyle("cell", parent=body, fontSize=8.7, leading=11, spaceAfter=0)
cellb = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold")
h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=INK, spaceBefore=11, spaceAfter=4, keepWithNext=1)
h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10.2, leading=13, textColor=SIGNAL, spaceBefore=6, spaceAfter=2.5, keepWithNext=1)
title = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=INK, spaceAfter=2)
subtitle = ParagraphStyle("subtitle", parent=body, fontSize=10.2, leading=13.5, textColor=INK2, spaceAfter=6)
formula = ParagraphStyle("formula", parent=body, fontName="Courier", fontSize=8.4, leading=11, backColor=ICE, borderPadding=(3, 5, 3, 5), spaceBefore=3, spaceAfter=8, leftIndent=5, rightIndent=5)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=10, bulletIndent=1, spaceAfter=2.5)


def P(text, style=body):
    return Paragraph(text, style)


def bullets(items):
    return [Paragraph(t, bullet, bulletText="•") for t in items]


def table(rows, widths, header=True, align_right_from=None):
    data = []
    for i, row in enumerate(rows):
        data.append([Paragraph(str(c), cellb if (i == 0 and header) else cell) for c in row])
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    t.setStyle(TableStyle(style))
    return t


def img(path, width_mm):
    from PIL import Image as PILImage
    w, h = PILImage.open(path).size
    return Image(str(path), width=width_mm * mm, height=width_mm * mm * h / w)


def side_by_side(left, right, w_left=85, w_right=85):
    t = Table([[left, right]], colWidths=[w_left * mm, w_right * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


pc = lambda x: f"{x * 100:.0f}%"
signed = lambda x: f"{(0.0 if abs(x) < 0.05 else x):+.1f}"
s = R["summary"]
clean, raw, weighted = s["clean"], s["contaminated_unweighted"], s["contaminated_weighted"]
track_d, track_n = R["tracking"]["with_drift"][-1], R["tracking"]["no_drift"][-1]
plan = R["plan_study"]
collab = R["collab_personas"]
safety = R["safety"]
proj = R["projection_coverage"]

story = []

story += [
    P("AI4Brain: a cognitive growth agent that shows its doubt", title),
    P("Technical report for the CISTAC 1.0 AI4Brain challenge, Phase 1. Team: [team name]. Members: [member names]. Code: github.com/ahmedmakni-sys/k6-abdo_the_chair-CHLAMPY", subtitle),
    P(f"<b>Summary.</b> AI4Brain assesses ten thinking skills through adaptive tasks, keeps a historised Brain Twin in which every score carries a 90% credible range, "
      f"coaches in plain language from evidence it can show, and builds a plan that changes after each session. Code measures and decides, and language models only phrase. "
      f"The coach therefore runs offline and cannot state what the evidence does not support. On simulated learners, true values fell inside the 90% range {pc(clean['coverage_90'])} of the time, "
      f"with an error of {clean['rmse_points']:.1f} points after one session. Under careless responding, evidence weighting cut error from {raw['rmse_points']:.1f} to {weighted['rmse_points']:.1f} points. "
      f"These checks show that the machinery is sound. It has not yet been validated with people, and section 9 says what that does and does not mean."),
]

story += [
    P("1. Objective and scope", h1),
    P("The challenge asks for an agent that can assess, understand, coach and improve, non-clinically. The table shows how each requirement is met."),
    table([
        ["Requirement", "How AI4Brain meets it", "Code"],
        ["Assess (Layer A)", "Ten skills, two tasks each (two sources for self-monitoring). Score, response time, error rate and behaviour are recorded per item. Assessment is non-biometric only.", "items.py, engine.py"],
        ["Understand", "Bayesian item response model gives a percentage and a 90% credible range for every skill. Careless trials count for less.", "estimator.py, behaviour.py"],
        ["Brain Twin", "Immutable snapshot history, a timeline slider and optional projections given only as ranges.", "twin.py"],
        ["Coach (Layer B)", "Deterministic insights with visible evidence, phrased by a built-in writer or Claude, and checked by a safety filter. No clinical terms.", "coach.py, guard.py"],
        ["Improve (Layer C)", "Adaptive difficulty, versioned plans with reasons, radar chart, progress curves, two heatmaps and probabilistic goal tracking.", "planner.py, web/"],
        ["AI Collaboration Score", "Behavioural 0-100 score from eight scripted rounds with planted flaws, using the proposed weights, with interval and weight sensitivity.", "collab.py"],
        ["Ethics and data", "Purpose-based consent, chosen retention, one-click deletion and export.", "storage.py, docs/ETHICS.md"],
        ["Bonus (Layer D)", "Voice coaching in the browser, state-aware pacing without biometrics, and growth projections with uncertainty.", "web/app.js, behaviour.py, twin.py"],
    ], [33, 108, 34]),
    Spacer(1, 4),
    P("<b>A gap in the brief.</b> The brief refers to \"the cognitive dimensions listed in Section 3\", but the published PDF contains no such list. "
      "We chose ten skills that cover focus, memory, speed, reasoning, flexibility, language, spatial thinking, decisions, creativity and self-monitoring. They live in a single registry, so the set can be changed quickly."),
]

story += [
    P("2. Architecture and why", h1),
    P("The pipeline runs in one direction: tasks in the browser produce trials, trials become weighted evidence, evidence updates the twin, rules turn the twin into insights, and only then does language appear."),
    table([
        ["Decision", "Reason"],
        ["Scores are computed, never generated", "A language model judging performance may vary between runs and cannot show its working. A Bayesian update can be replayed from the trial log."],
        ["Grid posterior with a 3PL item response model", "Exact uncertainty with no sampler, fractional outcomes and weights are easy to add, and it can be tested by parameter recovery. There is no human data to train a neural model on yet."],
        ["Evidence first, language second", "Every claim comes from code, so each message can show why it was made. A model failure degrades wording, not correctness."],
        ["Flask, SQLite, no-build JavaScript", "One command, offline, on any laptop. Trials are an append-only event log, so history stays auditable."],
        ["Optional Claude language layer", "Better phrasing where a user opts in and a key exists. The model receives summary numbers and a redacted question, and its replies pass the same filter."],
    ], [58, 117]),
]

dim_rows = [["Skill", "Tasks", "Guess floor", "Main known bias"]]
floors = {"attention": "50%", "working_memory": "none", "processing_speed": "50%", "logical_reasoning": "25%, 50%", "cognitive_flexibility": "50%", "verbal_reasoning": "25%", "spatial_reasoning": "25%", "decision_making": "50%", "creative_thinking": "none", "metacognition": "n/a"}
bias = {
    "attention": "Device latency, time of day, early practice effects",
    "working_memory": "Digit familiarity, typing speed, rehearsal strategies",
    "processing_speed": "Touch and slow hardware; normal differences with age",
    "logical_reasoning": "Maths schooling and test familiarity",
    "cognitive_flexibility": "Gaming experience",
    "verbal_reasoning": "English proficiency: the most language-dependent skill",
    "spatial_reasoning": "Practice opportunity, drawing and technical subjects",
    "decision_making": "Numeracy; risk attitudes are not judged",
    "creative_thinking": "Vocabulary, culture and author-chosen answer lists",
    "metacognition": "Modesty norms; the difficulty mix shifts calibration",
}
for k, d in DIMENSIONS.items():
    dim_rows.append([d["name"], ", ".join(t["name"] for t in d["tasks"]), floors[k], bias[k]])

story += [
    KeepTogether([P("3. Layer A: assessment and the Brain Twin", h1), table(dim_rows, [34, 54, 18, 69])]),
    Spacer(1, 3),
    P("Definition, tasks, scoring, uncertainty and biases are documented for each skill in docs/DIMENSIONS.md and on each skill's page in the app, both generated from the same registry.", small),
    P("Scoring model", h2),
    P("Each item has discrimination a, difficulty b from its level, and guess floor c. A trial gives a fractional outcome y and an evidence weight w:"),
    P("P(correct | theta) = c + (1 - c) * logistic(a * (theta - b))<br/>log posterior(theta) += w * [ y log P + (1 - y) log(1 - P) ]", formula),
    P("On speeded tasks y falls from 1 to 0.6 as a response approaches the deadline. Timeouts score zero. The weight w falls for trials too fast to have been read (x0.25), lost window focus (x0.3), long pauses (x0.6), timeouts (x0.8) and identical-answer runs (x0.5). Self-monitoring uses a proper scoring rule, y = max(0, 1 - 2(c - x)<super>2</super>), on stated confidence c and outcome x."),
    P("What the percentage means", h2),
    P("Percent is the expected score on a balanced reference test spanning all ten difficulty levels. It therefore has an operational meaning without a norm group, and the app says plainly that it is not a percentile. The range is the 5th to 95th percentile of the posterior mapped to that scale."),
    P("A dynamic, historised profile", h2),
    P("Every finished session writes an immutable snapshot, and the timeline slider replays them. Between sessions the posterior is diffused (variance +0.012 per day and +0.06 per session), so a skill you haven't practised shows a wider range, and the twin can follow someone who is improving. Abandoned sessions still count: their answered items are kept."),
    P("Projections are optional and never stated as fact. A Bayesian linear trend gives 50% and 90% ranges at 7, 14 and 30 days. It refuses to appear with fewer than three check-ins or less than three days of history, and is worded as a plausible range if practice continues in a similar way."),
    img(SHOTS / "twin.png", 132),
    P("Figure 1. Brain Twin of a simulated learner: estimate, 90% band, timeline, and a range for every skill.", small),
]

story += [
    P("4. Layer B: the AI coach", h1),
    P("Evidence builder. A compact packet of facts is built with no identifiers. Insight rules then detect patterns such as probable growth (judged by the probability of change, not the raw difference), speed at the cost of accuracy, late-session drops, switch costs, confidence running ahead of accuracy, wide ranges and stale evidence. Each insight stores the facts that triggered it, so the \"Why I'm saying this\" panel shows the actual cause."),
    P("Language. Replies come from a built-in writer that needs no network or, with opt-in and a key, from Claude (claude-opus-5-5 at low effort). Requests for health judgements, signs of serious distress and attempts to override instructions get fixed responses and never reach the model. Personal data is removed before storage and before any model call."),
    P("Safety filter. Every generated reply is checked for clinical vocabulary, claims of certainty about the future, and numbers absent from the evidence. A blocked model reply falls back to the built-in writer, so a model failure cannot reach the user."),
    P("<b>Example.</b> Asked \"Why did my spatial reasoning change?\", the coach gives the estimate, the range and the amount of evidence, says the last change is within the noise, and points to the items that moved the estimate. Asked \"Do these scores mean I have ADHD?\", it gives a fixed reply: it can't answer health questions, nothing here can tell them that, and a qualified professional is the right person to ask."),
    KeepTogether([img(SHOTS / "coach.png", 128), P("Figure 2. Coach chat with a fixed safety reply, evidence panel, and notes based on the user's own results.", small)]),
]

story += [
    P("5. Layer C: adaptive learning and dashboard", h1),
    P("Difficulty adaptation has two modes. A check-in picks the level with the most Fisher information at the current estimate and stops early once the estimate is tight. Practice picks the level with about 80% predicted success, just under the optimum reported by Wilson et al. (2019), and eases to 88% when a session looks hard going."),
    P("The plan is explainable arithmetic, and the plan page draws each term:"),
    P("priority = 0.35 goal_gap + 0.25 uncertainty + 0.20 staleness + 0.20 plateau", formula),
    P("Sessions are spaced and interleaved over seven days. Each one states why it is there and how the user will know it worked. Every session creates a new plan version recording what changed and why. Goals are tracked by probability: a goal counts as reached when P(percent at or above target) reaches 80%. The dashboard includes the radar chart, progress curves with uncertainty ribbons, a heatmap of estimates by week, a heatmap of success by difficulty, and goal tracking."),
    KeepTogether([img(SHOTS / "plan_priority.png", 128), P("Figure 3. The plan page shows how priorities are worked out, term by term, and what changed in each version.", small)]),
]

story += [
    P("6. AI Collaboration Score", h1),
    P("Self-reports of AI habits are unreliable, so the score comes from behaviour in eight scripted rounds where the assistant is sometimes wrong on purpose. Flaws are planted, so catching one is an observation. No language model is involved, which makes the score reproducible."),
    P("Score = 100 x (0.20 C + 0.25 V + 0.20 I + 0.20 A + 0.15 R)", formula),
    table([
        ["Component", "Weight", "Definition (shares use (s + 1) / (n + 2) smoothing)"],
        ["C Clarification", "20%", "Vague requests where a relevant question was asked before answering"],
        ["V Critical verification", "25%", "Hit rate on flawed steps minus false-alarm rate on sound steps, floored at 0. Blanket suspicion earns nothing"],
        ["I Iteration", "20%", "Flawed drafts improved by one or two targeted requests ending in a correct answer. Self-corrected rounds are left out"],
        ["A Autonomy", "20%", "Half own-answer-first rate, half appropriate reliance: the right final answer whether the AI was right or wrong"],
        ["R Responsible use", "15%", "Responsible-use questions handled well. Personal data typed into a question counts as a failure"],
    ], [42, 14, 119]),
    Spacer(1, 3),
    P("The weights are the brief's design proposal and are not validated. The app therefore reports a credible interval from Beta posteriors (4,000 draws), the range of the score when weights are redrawn around the proposal (Dirichlet, concentration 40), and the equal-weights score."),
    KeepTogether([img(SHOTS / "lab_debrief.png", 128), P("Figure 4. AI collaboration lab: debrief after a round, showing the planted flaws and the score with its range.", small)]),
]

story += [
    P("7. Bonus features", h1),
    *bullets([
        "<b>Voice-based coaching.</b> Replies can be read aloud and questions spoken, through the browser's own speech services. It is off by default, carries words only, makes no voice print, and no audio reaches this app's server.",
        "<b>Emotion-aware pacing, without biometrics.</b> A state proxy reads response patterns (error streaks, late-session slowing, timeouts) and an optional one-tap mood. It can ease difficulty and change coaching tone, and it never changes a score. We chose not to infer emotion from a face or voice, because that inference is unreliable and the brief bars sensitive decisions on it.",
        "<b>Predictive cognitive growth.</b> Projection ranges are described in section 3 and evaluated in section 9.",
    ]),
]

story += [
    P("8. Ethics and data", h1),
    *bullets([
        "<b>Consent</b> is requested before anything is stored and is split by purpose. Storage is required for a profile, while Claude and voice are off by default. Choices are time-stamped and can be changed at any time.",
        "<b>Retention.</b> Users choose 30 days to one year of inactivity (180 days by default). Expired profiles are removed when the server starts.",
        "<b>Deletion and export.</b> Delete removes every row for the profile, tested for all tables. Export gives everything held, as JSON.",
        "<b>Minimisation.</b> No name, email or account. A random ID, on a local database. No camera, audio recording or biometric data, and no decision of any kind uses face or voice.",
    ]),
]

rec_rows = [["Skill", "Error (RMSE)", "Bias", "r", "90% coverage", "Range width"]]
for d, v in R["recovery_clean"].items():
    rec_rows.append([DIMENSIONS[d]["name"], f"{v['rmse_points']:.1f}", signed(v["bias_points"]), f"{v['pearson_r']:.2f}", pc(v["coverage_90"]), f"{v['mean_width']:.0f}"])
rec_rows.append(["<b>Mean</b>", f"<b>{clean['rmse_points']:.1f}</b>", f"<b>{signed(clean['bias_points'])}</b>", f"<b>{clean['pearson_r']:.2f}</b>", f"<b>{pc(clean['coverage_90'])}</b>", f"<b>{clean['mean_width']:.0f}</b>"])

gen_rows = [["Learners differ from the model", "Error", "Bias", "Coverage"]]
for name, m in R["generalisation"].items():
    gen_rows.append([name, f"{m['rmse_points']:.1f}", signed(m["bias_points"]), pc(m["coverage_90"])])

labels = dict(careful_partner="Careful partner", average_user="Average user", over_sceptic="Over-sceptic", blind_accepter="Blind accepter", full_delegator="Full delegator")

story += [
    P("9. Evaluation", h1),
    P("<b>Every result here comes from simulated learners</b>, using scripts/run_eval.py. These checks show that the machinery behaves as designed. They are not evidence that the scores are valid for real people. All values are in percentage points unless noted, for one assessment session of up to 16 items."),
    P("Recovering a known ability", h2),
    table(rec_rows, [55, 26, 18, 18, 30, 28]),
    Spacer(1, 3),
    P("<b>A defect this caught.</b> The first run showed working memory biased by +16 points, with only 36% of true values inside the range. Generous partial credit was being read as success. We removed it from the estimator, keeping it as feedback only, and the skill now matches the others. The evaluation is doing its job when it finds things like this."),
    KeepTogether([
        side_by_side(
            [P("Careless responding", h2), img(FIG / "robustness.png", 80),
             P(f"Learners rush 15% of items, lapse on 10% and lose focus on 10%. Weighting raised coverage from {pc(raw['coverage_90'])} to {pc(weighted['coverage_90'])}.", small)],
            [P("Tracking a learner who is improving", h2), img(FIG / "tracking.png", 80),
             P(f"With drift, coverage at session 10 is {pc(track_d['coverage_90'])}; without it, {pc(track_n['coverage_90'])}. The estimate still lags fast improvers ({track_d['bias_points']:+.1f} points).", small)],
        ),
    ]),
    P("When the model is wrong (generalisation proxy)", h2),
    table(gen_rows, [90, 28, 28, 29]),
    Spacer(1, 3),
    P("Wrong difficulty values bias estimates by about 5 points in the expected direction, and this is why calibrating difficulty on real data comes first on the roadmap."),
    P("Projections, plan and collaboration score", h2),
    P(f"<b>Projections.</b> 90% ranges covered the true future value {pc(proj['7']['coverage_90'])}, {pc(proj['14']['coverage_90'])} and {pc(proj['30']['coverage_90'])} of the time at 7, 14 and 30 days, so longer horizons are conservative. "
      f"<b>Plan.</b> Over 28 simulated days, with a goal 8 points above the starting level, the goal was reached by {pc(plan['planner']['goal_reached'])} of learners on the plan, {pc(plan['random']['goal_reached'])} on random skills and {pc(plan['weakest_only']['goal_reached'])} always practising the two weakest, while the plan kept range widths about the same as random. Practice helps by construction here, so this tests how sessions are allocated, not whether practice helps people. "
      f"<b>Collaboration score.</b> Personas ordered as intended: " + ", ".join(f"{labels[k]} {collab[k]['mean']:.0f}" for k in sorted(collab, key=lambda p: -collab[p]["mean"])) + ". Over-sceptics are penalised for false alarms."),
    P(f"<b>Safety.</b> The filter handled {safety['medical']['handled']} of {safety['medical']['prompts']} health-judgement requests, {safety['distress']['handled']} of {safety['distress']['prompts']} distress statements, {safety['injection']['handled']} of {safety['injection']['prompts']} override attempts and {safety['personal_data']['handled']} of {safety['personal_data']['prompts']} personal-data messages, and blocked {safety['benign']['wrongly_blocked']} of {safety['benign']['prompts']} ordinary questions. "
      f"A scan of {safety['output_scan']['messages_checked']} generated messages across {safety['output_scan']['profiles']} profiles found {safety['output_scan']['flagged']} with clinical terms or claims of certainty. We wrote these batteries ourselves, so they are regression tests, not an independent red team, and a pattern filter can be evaded by wording it has not seen."),
    P("The test suite (pytest) passes in full and covers malformed input, duplicate and invalid requests, deletion, retention, and the model path through a stub client."),
]

story += [
    P("10. Limitations and next steps", h1),
    *bullets([
        "<b>No validation with people.</b> Validity, reliability and fairness are unknown, and real learning gains are unmeasured. The percentage should not be read as a statement about a person's ability in general.",
        "<b>Difficulty levels are design values.</b> A pilot study should calibrate them and replace the a-priori parameters, then measure test-retest reliability and compare against established tasks.",
        "<b>Language.</b> Verbal tasks assume English, which disadvantages non-native speakers. Reviewed Arabic and French item banks are the first content priority.",
        "<b>The live Claude path is untested.</b> No API key was available during development, so that path has only run against a stub. The built-in coach is what the demo shows.",
        "<b>Task bank and scoring.</b> The verbal banks are finite, and creative scoring is a low-reliability heuristic, which is reflected in its capped evidence weight.",
        "<b>Security.</b> A random ID suits a local tool. A hosted version needs real authentication and encryption at rest.",
    ]),
    P("References", h1),
    P("Birnbaum (1968), latent trait models, in Lord and Novick, Statistical Theories of Mental Test Scores. "
      "Brier (1950), Monthly Weather Review 78(1). "
      "Eriksen and Eriksen (1974), Perception and Psychophysics 16. "
      "Guilford (1967), The Nature of Human Intelligence. "
      "Lee and See (2004), Human Factors 46(1). "
      "Mednick (1962), Psychological Review 69(3). "
      "Monsell (2003), Trends in Cognitive Sciences 7(3). "
      "Shepard and Metzler (1971), Science 171. "
      "Tversky and Kahneman (1974), Science 185. "
      "van der Linden and Glas (2010), Elements of Adaptive Testing. "
      "Wilson et al. (2019), The Eighty Five Percent Rule for optimal learning, Nature Communications 10. "
      "Wise and Kong (2005), Applied Measurement in Education 18(2).", small),
]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(INK2)
    canvas.drawString(17.5 * mm, 9 * mm, "AI4Brain technical report")
    canvas.drawRightString(A4[0] - 17.5 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=17.5 * mm, rightMargin=17.5 * mm, topMargin=14 * mm, bottomMargin=15 * mm,
                            title="AI4Brain technical report", author="AI4Brain team", subject="CISTAC 1.0 AI4Brain challenge, Phase 1")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    pages = len(PdfReader(str(OUT)).pages)
    print(f"{OUT.name}: {pages} pages")
    if pages > 8:
        raise SystemExit("The report exceeds the 8-page limit")


if __name__ == "__main__":
    main()
