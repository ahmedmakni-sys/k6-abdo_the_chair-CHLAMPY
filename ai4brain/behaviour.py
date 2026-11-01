"""Behaviour signals: evidence weighting, session statistics, and the state proxy.

Nothing here uses a camera, a microphone or any biometric. The state proxy reads only
response patterns and a one-tap self-report, and it can change pacing and coaching tone
but never a score. A wrong guess about someone's state therefore costs very little.
"""

from statistics import mean, median

from .items import RT_FLOOR_MS


def trial_weight(item, rt_ms, focus_lost, responses_so_far, rts_so_far, timed_out):
    """Return (weight, flags). Weight in [0, 1] scales how much a trial moves the estimate."""
    flags = []
    w = 1.0
    floor = RT_FLOOR_MS.get(item["kind"], 150)
    if not timed_out and rt_ms is not None and rt_ms < floor:
        flags.append("too_fast")
        w *= 0.25
    if focus_lost:
        flags.append("focus_lost")
        w *= 0.3
    if rts_so_far and rt_ms is not None and not item.get("speeded") and len(rts_so_far) >= 3:
        if rt_ms > 4 * median(rts_so_far):
            flags.append("long_pause")
            w *= 0.6
    if timed_out:
        flags.append("timeout")
        w *= 0.8
    if len(responses_so_far) >= 7 and len(set(responses_so_far[-7:])) == 1 and item["kind"] == "choice":
        flags.append("same_answer_run")
        w *= 0.5
    return round(w, 3), flags


def _thirds(values):
    n = len(values)
    k = max(1, n // 3)
    return values[:k], values[-k:]


def session_stats(trials):
    """Summarise answered trials: accuracy, speed pattern, drift, switch and focus costs."""
    done = [t for t in trials if t.get("correct") is not None]
    if not done:
        return dict(n=0)
    rts = [t["rt_ms"] for t in done if t.get("rt_ms")]
    correct_rts = [t["rt_ms"] for t in done if t["correct"] and t.get("rt_ms")]
    ratios = [t["rt_ms"] / t["deadline_ms"] for t in done if t.get("rt_ms") and t.get("deadline_ms")]
    acc = mean(1.0 if t["correct"] else 0.0 for t in done)
    stats = dict(
        n=len(done),
        accuracy=round(acc, 3),
        error_rate=round(1 - acc, 3),
        median_rt_ms=round(median(rts)) if rts else None,
        median_rt_correct_ms=round(median(correct_rts)) if correct_rts else None,
        rt_of_deadline=round(median(ratios), 3) if ratios else None,
        timeouts=sum(1 for t in done if "timeout" in t["flags"]),
        too_fast=sum(1 for t in done if "too_fast" in t["flags"]),
        focus_lost=sum(1 for t in done if "focus_lost" in t["flags"]),
        same_answer_runs=sum(1 for t in done if "same_answer_run" in t["flags"]),
        data_quality=round(mean(t["w"] for t in done), 3),
        mean_level=round(mean(t["level"] for t in done), 2),
        speeded=any(t.get("speeded") for t in done),
    )
    streak = best = 0
    for t in done:
        streak = streak + 1 if not t["correct"] else 0
        best = max(best, streak)
    stats["longest_error_streak"] = best

    if len(done) >= 6:
        first, last = _thirds(done)
        stats["accuracy_first_third"] = round(mean(1.0 if t["correct"] else 0.0 for t in first), 3)
        stats["accuracy_last_third"] = round(mean(1.0 if t["correct"] else 0.0 for t in last), 3)
        first_rt = [t["rt_ms"] for t in first if t.get("rt_ms")]
        last_rt = [t["rt_ms"] for t in last if t.get("rt_ms")]
        if first_rt and last_rt:
            stats["slowing_ratio"] = round(mean(last_rt) / mean(first_rt), 3)

    switch = [t["rt_ms"] for t in done if t.get("meta", {}).get("is_switch") and t["correct"] and t.get("rt_ms")]
    repeat = [t["rt_ms"] for t in done
              if t.get("meta", {}).get("is_switch") is False and t["correct"] and t.get("rt_ms")]
    if len(switch) >= 4 and len(repeat) >= 4:
        stats["switch_cost_ms"] = round(mean(switch) - mean(repeat))
        stats["switch_trials"] = len(switch)

    incon = [t["rt_ms"] for t in done if t.get("meta", {}).get("incongruent") and t["correct"] and t.get("rt_ms")]
    congr = [t["rt_ms"] for t in done
             if t.get("meta", {}).get("incongruent") is False and t["correct"] and t.get("rt_ms")]
    if len(incon) >= 3 and len(congr) >= 3:
        stats["distractor_cost_ms"] = round(mean(incon) - mean(congr))

    rated = [t for t in done if t.get("confidence") is not None]
    if rated:
        stats["rated"] = len(rated)
        stats["mean_confidence"] = round(mean(t["confidence"] for t in rated), 3)
        stats["rated_accuracy"] = round(mean(1.0 if t["correct"] else 0.0 for t in rated), 3)
    return stats


def state_proxy(stats, mood=None):
    """A behaviour-and-self-report estimate of how the session is going for this person."""
    signals, strain = [], 0.0
    if mood in ("tired", "frustrated"):
        signals.append(f"you told me you felt {mood}")
        strain += 0.45
    if stats.get("n", 0) >= 3:
        if stats.get("longest_error_streak", 0) >= 3:
            signals.append(f"{stats['longest_error_streak']} errors in a row")
            strain += 0.3
        first, last = stats.get("accuracy_first_third"), stats.get("accuracy_last_third")
        if first is not None and last is not None and first - last >= 0.25:
            signals.append("accuracy dropped towards the end of the session")
            strain += 0.25
        if stats.get("slowing_ratio", 1.0) >= 1.25:
            signals.append("responses slowed towards the end of the session")
            strain += 0.2
        if stats.get("timeouts", 0) >= max(2, stats["n"] // 4):
            signals.append("several responses ran out of time")
            strain += 0.2
    strain = min(1.0, strain)
    state = "strained" if strain >= 0.6 else "tiring" if strain >= 0.3 else "steady"
    return dict(
        state=state,
        strain=round(strain, 2),
        signals=signals,
        basis="Response patterns and your self-report only. No camera, voice or biometric data.",
        effect="Can change pacing and coaching tone. It never changes a score.",
    )


def success_target(mood=None, proxy=None):
    """Target success rate for training. Eases off when the session is hard going."""
    if mood in ("tired", "frustrated") or (proxy and proxy["state"] != "steady"):
        return 0.88
    if mood == "energised":
        return 0.76
    return 0.80
