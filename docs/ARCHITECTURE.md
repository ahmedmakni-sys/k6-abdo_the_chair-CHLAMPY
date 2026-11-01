# Architecture and why it looks this way

The brief asks for a coach with a "free but justified architecture". The central decision is **evidence first, language second**: code measures and decides, and language models only phrase. Everything else follows from that.

```
 Browser (web/)                    Server (ai4brain/)
 ┌───────────────────┐            ┌─────────────────────────────────────────────┐
 │ Task renderers    │  item      │ items.py      generators and scoring        │
 │ measure RT, focus ├──────────► │ behaviour.py  evidence weights, state proxy │
 │                   │  response  │ estimator.py  Bayesian grid, 3PL, drift     │
 │ Twin dashboard    │ ◄──────────┤ engine.py     sessions, stop rule, snapshots│
 │ radar, curves,    │  twin      │ twin.py       history, goals, projections   │
 │ heatmaps, goals   │            │ planner.py    versioned, explained plans    │
 │                   │            │ collab.py     AI Collaboration Score        │
 │ Coach chat        │  message   │ coach.py      evidence, insights, language  │
 │ voice in browser  ├──────────► │ guard.py      input and output safety       │
 │                   │  reply     │ storage.py    SQLite, retention, deletion   │
 └───────────────────┘            └─────────────────────────────────────────────┘
                                         │ only with opt-in and an API key:
                                         ▼ summary numbers and a redacted question
                                     Claude (language layer only)
```

## Decisions

### Scores are computed, never generated

A language model asked to judge performance may give different answers on different days and cannot show its working. Each estimate here comes from a Bayesian update that can be replayed from the trial log, so it is reproducible and auditable.

### Discrete-grid Bayesian IRT

Each dimension holds a posterior over latent ability on a 161-point grid. Items follow a 3PL model, `P(correct) = c + (1 - c) * logistic(a(theta - b))`.

- **Why a grid:** exact posteriors with no sampler and no heavy dependency, and any likelihood shape works, including fractional outcomes and evidence weights.
- **Why IRT:** difficulty and ability sit on one scale, so adaptive selection, success prediction and goal probabilities all come from one model.
- **Why not a neural model:** there is no human training data yet, and a simple generative model can be checked by parameter recovery.

### What the percentage means

`percent = expected score on a balanced reference test spanning the 10 difficulty levels`.

It has an operational meaning that does not need a norm group. It is not a percentile, because there is no population sample to compare with, and the interface says so wherever a score appears.

### Uncertainty is a first-class output

- A 90% credible interval comes straight from the posterior and is drawn on every score.
- Evidence weights reduce the influence of untrustworthy trials: too fast to have been read (×0.25), lost window focus (×0.3), long pause (×0.6), timeout (×0.8), identical-answer run (×0.5).
- Between sessions the posterior diffuses (`var += 0.012 per day + 0.06 per session`), so old evidence counts for less and the band widens. That also lets the twin follow someone who is improving.

### Two kinds of adaptation

- **Check-in mode** picks the most informative level, by maximum Fisher information at the current estimate, and stops early once the estimate is tight.
- **Practice mode** picks the level with about 80% predicted success, just under the optimum reported by Wilson et al. (2019). It rises to 88% when the session looks hard going.

### The coach cannot state what the evidence does not support

1. `build_evidence` creates a compact fact packet with no identifiers.
2. `detect_insights` applies deterministic rules. Each insight stores the facts that triggered it, so the "Why I'm saying this" panel is the actual cause and not a post-hoc story.
3. The language layer is Claude when the user has opted in and a key is configured, otherwise a built-in writer.
4. `guard.check_output` blocks clinical vocabulary, claims of certainty about the future and numbers absent from the evidence. A blocked reply falls back to the built-in writer.

The result is that the coach works with no network, is safe when the model misbehaves, and costs nothing to run in the default mode.

When enabled, the language layer calls `claude-opus-5-5` through the official `anthropic` SDK at low effort, with the server-side fallback option turned on for refusals. Refusals and API errors are handled by falling back to the built-in writer. This path is covered by unit tests with a stub client. It has not been exercised against the live API, because no key was available during development.

### Plans are explainable arithmetic

`priority = 0.35 goal_gap + 0.25 uncertainty + 0.20 staleness + 0.20 plateau`. The plan page draws each term. Sessions are interleaved and spaced, each one carries a success measure, and every version records what changed and why.

### Behaviour, not biometrics

The mandatory non-biometric mode is the only mode for assessment. The state proxy reads response patterns and a one-tap self-report, and can change pacing and tone but never a score. Voice is optional and handled by the browser's own speech services, for words only.

### Flask, SQLite and vanilla JavaScript

The jury should be able to run it in one command, offline, on any laptop. There is no build step, no CDN and no external service. Trials are an append-only event log, and snapshots are immutable, so history cannot be rewritten by later processing.

## Generalising beyond this brief

The dimensions, tasks and block plans live in `ai4brain/dimensions.py` and `engine.BLOCKS`. Adding a dimension takes a registry entry and a generator. Every other layer reads from the registry, including documentation, the dashboard and the planner. Task parameters are in one table, ready to be replaced by empirically calibrated values once human data exists.
