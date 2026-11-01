"""Synthetic learners for evaluating the estimator, the planner and the demo.

All figures produced with this module describe behaviour on simulated people. They show
the machinery is internally sound; they say nothing about validity on real humans.
"""

import math
import random

from . import estimator as est, items


class SimUser:
    """A simulated person with a true ability per dimension and a response style."""

    def __init__(self, thetas, seed=0, rushed=0.0, lapse=0.0, overconfidence=0.0, rt_scale=1.0, a_scale=1.0,
                 disengaged=0.0, b_shift=0.0):
        self.thetas = dict(thetas)
        self.rng = random.Random(seed)
        self.rushed = rushed          # chance of a very fast random response
        self.lapse = lapse            # chance of a slow, attention-lost response
        self.overconfidence = overconfidence
        self.rt_scale = rt_scale
        self.a_scale = a_scale        # model misspecification: true discrimination differs
        self.disengaged = disengaged  # chance of tabbing away during a trial
        self.b_shift = b_shift        # model misspecification: real difficulty differs from the design value

    def p_correct(self, item):
        theta = self.thetas[item["dimension"]]
        return float(est.item_prob(theta, item["a"] * self.a_scale, item["b"] + self.b_shift, item["c"]))

    def respond(self, item):
        """Return (response, rt_ms, focus_lost, confidence)."""
        kind = item["kind"]
        focus_lost = self.rng.random() < self.disengaged
        p = self.p_correct(item)
        rushed = self.rng.random() < self.rushed
        lapse = not rushed and self.rng.random() < self.lapse
        if rushed:
            p = item["c"] if item["c"] > 0 else 0.05
        correct = self.rng.random() < p
        deadline = item.get("deadline_ms") or 10000
        # Typical response uses about half the deadline at matched difficulty, faster when easier.
        theta = self.thetas[item["dimension"]]
        base = 0.45 * deadline * math.exp(-0.25 * (theta - item["b"])) * self.rt_scale
        if not item.get("speeded"):
            base = min(base, 9000.0) * 0.9
        rt = base * math.exp(self.rng.gauss(0.0, 0.25))
        if rushed:
            rt = self.rng.uniform(60, 140) if kind in ("choice", "go_nogo") else self.rng.uniform(200, 500)
        if lapse:
            rt *= 4.5
            correct = correct and self.rng.random() < 0.6
        response = self._response_for(item, correct)
        timed_out = item.get("speeded") and rt > deadline
        if timed_out:
            response = None
            rt = float(deadline)
        confidence = None
        if item.get("ask_confidence"):
            felt = p if self.rng.random() < 0.7 else (1.0 if correct else 0.4)
            confidence = min(1.0, max(0.0, felt + self.overconfidence + self.rng.gauss(0.0, 0.08)))
        return response, rt, focus_lost, confidence

    def _response_for(self, item, correct):
        task, kind, answer = item["task"], item["kind"], item["answer"]
        if kind == "go_nogo":
            return "go" if (answer == "go") == correct else None
        if kind == "choice":
            if correct:
                return answer
            return next(c["key"] for c in item["payload"]["choices"] if c["key"] != answer)
        if kind == "recall":
            if correct:
                return answer
            digits = list(answer)
            i = self.rng.randrange(len(digits))
            digits[i] = str((int(digits[i]) + 1) % 10)
            return "".join(digits)
        if kind == "mcq":
            if correct:
                return answer
            return next(o for o in item["payload"]["options"] if o != answer)
        if task == "word_link":
            return answer[0] if correct else "something"
        # Unusual uses: idea count and originality track ability.
        count = max(1, int(2 + 2.0 * (self.thetas[item["dimension"]] + 2)))
        common = sorted(items.ALT_USES_OBJECTS[answer])
        rare = ["puppet theatre", "bird feeder", "garden sculpture", "tiny stage", "sun dial", "art stamp",
                "rain gauge", "wind chime", "chess piece", "plant marker", "stencil guide", "toy bridge"]
        ideas = []
        for i in range(count):
            if self.rng.random() < 0.5 + 0.15 * self.thetas[item["dimension"]]:
                ideas.append(rare[i % len(rare)])
            else:
                ideas.append(common[i % len(common)])
        return "\n".join(ideas)


def run_estimation(user, dimension, task, n_trials, adaptive=True, use_weights=True, rng=None):
    """Run a bare assessment without storage. Returns the final posterior."""
    from . import behaviour

    rng = rng or random.Random(0)
    posterior = est.Posterior()
    params = items.TASK_PARAMS[task]
    ctx, responses, rts = {}, [], []
    for i in range(n_trials):
        if adaptive:
            level = est.choose_level_for_information(posterior, params["a"], params["c"], rng)
        else:
            level = (i % est.LEVELS) + 1
        item = items.generate(task, level, rng, ctx)
        ctx.update(item.pop("ctx_update", {}))
        item["ask_confidence"] = False
        response, rt, focus_lost, _ = user.respond(item)
        scored = items.score_response(item, response, rt)
        weight, _ = behaviour.trial_weight(item, rt, focus_lost, responses, rts, scored["timed_out"])
        weight = min(weight, params["cap"])
        posterior.update(item["a"], item["b"], item["c"], scored["y"], weight if use_weights else 1.0)
        responses.append(response or "")
        rts.append(rt)
    return posterior
