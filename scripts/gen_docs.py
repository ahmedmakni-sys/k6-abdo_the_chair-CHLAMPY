"""Generate docs/DIMENSIONS.md from the registry and docs/EVALUATION.md from evaluation results."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai4brain.dimensions import DIMENSIONS  # noqa: E402
from ai4brain.engine import BLOCKS  # noqa: E402


def dimensions_md():
    out = [
        "# Cognitive dimensions",
        "",
        "Generated from `ai4brain/dimensions.py`. Do not edit by hand.",
        "",
        "> **Design decision.** The challenge brief refers to \"the cognitive dimensions listed in Section 3\", but the "
        "published PDF contains no such list. We chose these ten because together they cover the skills most often "
        "named in cognitive training and in the brief's own framing: focus, memory, speed, reasoning, flexibility, "
        "language, spatial thinking, decisions, creativity and self-monitoring. The set lives in one registry and can "
        "be changed in minutes if the committee's list differs.",
        "",
        "All scores share one model: 3PL item response with a Bayesian grid posterior, reported as a percentage with a "
        "90% credible interval. The percentage is the expected share of a balanced practice set solved. It is not a "
        "percentile. Difficulty levels are expert-set design values, not yet calibrated on people.",
        "",
    ]
    for key, d in DIMENSIONS.items():
        out += [f"## {d['name']}", "", f"*{d['plain']}*", "", f"**Definition.** {d['definition']}", "", "**Tasks.**", ""]
        out += [f"- **{t['name']}**: {t['how']}" for t in d["tasks"]]
        count = sum(c for _, c in BLOCKS[key])
        out += [
            "",
            f"**Session length.** Up to {count} items per session.",
            "",
            f"**Scoring.** {d['scoring']}",
            "",
            f"**Uncertainty.** {d['uncertainty']}",
            "",
            f"**Known biases.** {d['biases']}",
            "",
        ]
    return "\n".join(out)


def evaluation_md(r):
    s = r["summary"]
    pct = lambda x: f"{x * 100:.0f}%"
    signed = lambda x: f"{(0.0 if abs(x) < 0.05 else x):+.1f}"
    out = [
        "# Evaluation",
        "",
        "Generated from `docs/evaluation_results.json` by `scripts/gen_docs.py`. Reproduce with `python scripts/run_eval.py`.",
        "",
        "> **Every number here comes from simulated learners.** These checks show the machinery is internally sound. "
        "They are not evidence that the scores are valid for real people. That needs a study with human participants, "
        "which has not been done.",
        "",
        "## Can it recover a known ability?",
        "",
        "Simulated learners with known ability complete one assessment session per dimension.",
        "",
        "| Dimension | Error (RMSE, points) | Bias (points) | Correlation | True value in 90% range | Mean range width |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for d, v in r["recovery_clean"].items():
        out.append(f"| {DIMENSIONS[d]['name']} | {v['rmse_points']:.1f} | {signed(v['bias_points'])} | {v['pearson_r']:.2f} | {pct(v['coverage_90'])} | {v['mean_width']:.0f} |")
    c = s["clean"]
    out += [
        f"| **Mean** | **{c['rmse_points']:.1f}** | **{signed(c['bias_points'])}** | **{c['pearson_r']:.2f}** | **{pct(c['coverage_90'])}** | **{c['mean_width']:.0f}** |",
        "",
        "Coverage slightly above 90% means the ranges are a little conservative, which is the safer direction for this use.",
        "",
        "Self-monitoring is excluded here because it has no single true value in this simulation. It is exercised by the end-to-end tests.",
        "",
        "## A defect this evaluation found",
        "",
        "The first run showed working memory biased by +16 points, with only 36% of true values inside the 90% range. "
        "The cause was generous partial credit for recall, which the model read as evidence of full success. Partial "
        "credit was removed from the estimator and kept as feedback only. Working memory now behaves like the other dimensions.",
        "",
        "## Does evidence weighting help with careless responding?",
        "",
        "Learners rush 15% of items, lapse on 10% and lose window focus on 10%.",
        "",
        "| Condition | Error (RMSE, points) | Bias (points) | True value in 90% range |",
        "|---|---:|---:|---:|",
    ]
    for label, key in (("Clean behaviour", "clean"), ("Contaminated, no weighting", "contaminated_unweighted"), ("Contaminated, with weighting", "contaminated_weighted")):
        m = s[key]
        out.append(f"| {label} | {m['rmse_points']:.1f} | {signed(m['bias_points'])} | {pct(m['coverage_90'])} |")
    out += [
        "",
        "## Does it hold when the model is wrong?",
        "",
        "These learners differ from what the model assumes. This is the closest available stand-in for generalisation until human data exists.",
        "",
        "| Condition | Error (RMSE, points) | Bias (points) | True value in 90% range |",
        "|---|---:|---:|---:|",
    ]
    for name, m in r["generalisation"].items():
        out.append(f"| {name} | {m['rmse_points']:.1f} | {signed(m['bias_points'])} | {pct(m['coverage_90'])} |")
    last_d, last_n = r["tracking"]["with_drift"][-1], r["tracking"]["no_drift"][-1]
    out += [
        "",
        "Wrong difficulty values bias the estimate by several points in the expected direction. This is the main reason calibrating difficulty on real data comes first in the roadmap.",
        "",
        "## Does the twin follow someone who is improving?",
        "",
        "True ability rises by 0.05 to 0.25 logits per session, over 10 sessions of 8 items.",
        "",
        "| Model | True value in 90% range at session 10 | Bias at session 10 (points) |",
        "|---|---:|---:|",
        f"| With drift (the app) | {pct(last_d['coverage_90'])} | {signed(last_d['bias_points'])} |",
        f"| Without drift | {pct(last_n['coverage_90'])} | {signed(last_n['bias_points'])} |",
        "",
        "The estimate still lags fast improvers slightly, so a small negative bias remains.",
        "",
        "## Are projection ranges honest?",
        "",
        "| Horizon | True value in the 90% projection range | Mean range width (points) |",
        "|---|---:|---:|",
    ]
    for days, v in r["projection_coverage"].items():
        out.append(f"| {days} days | {pct(v['coverage_90'])} | {v['mean_width']:.0f} |")
    out += [
        "",
        "Ranges widen with the horizon. Longer horizons are conservative. A learner in this simulation keeps a steady rate, so real people may vary more.",
        "",
        "## Does following the plan help?",
        "",
        "Over 28 days and two sessions a day, each session raises true ability a little, with diminishing returns. Each learner has one goal, set 8 points above their starting level.",
        "",
        "| Policy | Goal reached | True gain on the goal skill (points) | Mean range width at the end | True values in 90% range |",
        "|---|---:|---:|---:|---:|",
    ]
    names = dict(planner="The app's planner", random="Random skills", weakest_only="Always the two weakest")
    for key, label in names.items():
        p = r["plan_study"][key]
        out.append(f"| {label} | {pct(p['goal_reached'])} | {p['true_gain_goal']:.1f} | {p['mean_width']:.0f} | {pct(p['coverage'])} |")
    out += [
        "",
        "Practice helps here by construction, so this tests how the plan allocates sessions. It does not test whether practice helps people.",
        "",
        "## Does the AI Collaboration Score separate behaviours?",
        "",
        "| Behaviour persona | Mean score | SD | Mean interval width |",
        "|---|---:|---:|---:|",
    ]
    for key, v in sorted(r["collab_personas"].items(), key=lambda kv: -kv[1]["mean"]):
        out.append(f"| {key.replace('_', ' ').capitalize()} | {v['mean']:.1f} | {v['sd']:.1f} | {v['ci_width']:.1f} |")
    sf = r["safety"]
    out += [
        "",
        "## Safety checks",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| Requests for health judgements | {sf['medical']['handled']} of {sf['medical']['prompts']} refused |",
        f"| Statements suggesting serious distress | {sf['distress']['handled']} of {sf['distress']['prompts']} received the support message |",
        f"| Attempts to override instructions | {sf['injection']['handled']} of {sf['injection']['prompts']} refused |",
        f"| Messages containing personal data | {sf['personal_data']['handled']} of {sf['personal_data']['prompts']} detected and redacted |",
        f"| Ordinary questions blocked by mistake | {sf['benign']['wrongly_blocked']} of {sf['benign']['prompts']} |",
        f"| Clinical terms or claims of certainty in generated messages | {sf['output_scan']['flagged']} of {sf['output_scan']['messages_checked']} messages across {sf['output_scan']['profiles']} profiles |",
        "",
        "These batteries were written by the developers, so they are regression tests and not an independent red team. A pattern-based filter can be evaded by wording it has not seen.",
        "",
        "## Not yet evaluated",
        "",
        "- Validity, reliability and fairness with human participants.",
        "- Real learning gains.",
        "- Live Claude replies. That path is tested with a stub client because no API key was available during development.",
        "- Voice input across browsers.",
        "",
    ]
    return "\n".join(out)


def main():
    docs = ROOT / "docs"
    (docs / "DIMENSIONS.md").write_text(dimensions_md(), encoding="utf-8")
    results = docs / "evaluation_results.json"
    if results.exists():
        (docs / "EVALUATION.md").write_text(evaluation_md(json.loads(results.read_text(encoding="utf-8"))), encoding="utf-8")
    print("Docs written")


if __name__ == "__main__":
    main()
