# Evaluation

Generated from `docs/evaluation_results.json` by `scripts/gen_docs.py`. Reproduce with `python scripts/run_eval.py`.

> **Every number here comes from simulated learners.** These checks show the machinery is internally sound. They are not evidence that the scores are valid for real people. That needs a study with human participants, which has not been done.

## Can it recover a known ability?

Simulated learners with known ability complete one assessment session per dimension.

| Dimension | Error (RMSE, points) | Bias (points) | Correlation | True value in 90% range | Mean range width |
|---|---:|---:|---:|---:|---:|
| Attention | 9.7 | -0.3 | 0.81 | 95% | 38 |
| Working memory | 7.9 | +1.0 | 0.88 | 93% | 26 |
| Processing speed | 9.7 | -0.4 | 0.81 | 94% | 39 |
| Logical reasoning | 11.1 | +0.1 | 0.79 | 92% | 36 |
| Cognitive flexibility | 9.5 | -1.3 | 0.83 | 93% | 37 |
| Verbal reasoning | 10.3 | -0.3 | 0.81 | 90% | 35 |
| Spatial reasoning | 9.4 | -0.7 | 0.81 | 91% | 34 |
| Decision making | 12.4 | -1.2 | 0.69 | 92% | 44 |
| Creative thinking | 10.7 | +2.9 | 0.72 | 97% | 46 |
| **Mean** | **10.1** | **+0.0** | **0.80** | **93%** | **37** |

Coverage slightly above 90% means the ranges are a little conservative, which is the safer direction for this use.

Self-monitoring is excluded here because it has no single true value in this simulation. It is exercised by the end-to-end tests.

## A defect this evaluation found

The first run showed working memory biased by +16 points, with only 36% of true values inside the 90% range. The cause was generous partial credit for recall, which the model read as evidence of full success. Partial credit was removed from the estimator and kept as feedback only. Working memory now behaves like the other dimensions.

## Does evidence weighting help with careless responding?

Learners rush 15% of items, lapse on 10% and lose window focus on 10%.

| Condition | Error (RMSE, points) | Bias (points) | True value in 90% range |
|---|---:|---:|---:|
| Clean behaviour | 10.1 | +0.0 | 93% |
| Contaminated, no weighting | 15.3 | -7.7 | 75% |
| Contaminated, with weighting | 12.7 | -4.0 | 87% |

## Does it hold when the model is wrong?

These learners differ from what the model assumes. This is the closest available stand-in for generalisation until human data exists.

| Condition | Error (RMSE, points) | Bias (points) | True value in 90% range |
|---|---:|---:|---:|
| Less discriminating items (a x 0.7) | 11.9 | -0.1 | 87% |
| More discriminating items (a x 1.3) | 8.6 | +1.6 | 98% |
| Items harder than designed (b + 0.5) | 11.0 | -4.5 | 88% |
| Items easier than designed (b - 0.5) | 11.2 | +5.9 | 92% |
| Slow device or style (RT x 1.5) | 9.3 | -0.5 | 94% |

Wrong difficulty values bias the estimate by several points in the expected direction. This is the main reason calibrating difficulty on real data comes first in the roadmap.

## Does the twin follow someone who is improving?

True ability rises by 0.05 to 0.25 logits per session, over 10 sessions of 8 items.

| Model | True value in 90% range at session 10 | Bias at session 10 (points) |
|---|---:|---:|
| With drift (the app) | 89% | -4.3 |
| Without drift | 20% | -10.5 |

The estimate still lags fast improvers slightly, so a small negative bias remains.

## Are projection ranges honest?

| Horizon | True value in the 90% projection range | Mean range width (points) |
|---|---:|---:|
| 7 days | 94% | 22 |
| 14 days | 98% | 30 |
| 30 days | 100% | 45 |

Ranges widen with the horizon. Longer horizons are conservative. A learner in this simulation keeps a steady rate, so real people may vary more.

## Does following the plan help?

Over 28 days and two sessions a day, each session raises true ability a little, with diminishing returns. Each learner has one goal, set 8 points above their starting level.

| Policy | Goal reached | True gain on the goal skill (points) | Mean range width at the end | True values in 90% range |
|---|---:|---:|---:|---:|
| The app's planner | 100% | 14.3 | 29 | 91% |
| Random skills | 18% | 5.3 | 28 | 91% |
| Always the two weakest | 38% | 5.9 | 36 | 90% |

Practice helps here by construction, so this tests how the plan allocates sessions. It does not test whether practice helps people.

## Does the AI Collaboration Score separate behaviours?

| Behaviour persona | Mean score | SD | Mean interval width |
|---|---:|---:|---:|
| Careful partner | 77.1 | 4.3 | 20.9 |
| Average user | 46.9 | 8.5 | 24.1 |
| Over sceptic | 43.5 | 6.7 | 22.7 |
| Blind accepter | 20.8 | 3.9 | 19.6 |
| Full delegator | 16.5 | 2.0 | 18.5 |

## Safety checks

| Check | Result |
|---|---|
| Requests for health judgements | 13 of 13 refused |
| Statements suggesting serious distress | 5 of 5 received the support message |
| Attempts to override instructions | 7 of 7 refused |
| Messages containing personal data | 3 of 3 detected and redacted |
| Ordinary questions blocked by mistake | 0 of 12 |
| Clinical terms or claims of certainty in generated messages | 0 of 510 messages across 60 profiles |

These batteries were written by the developers, so they are regression tests and not an independent red team. A pattern-based filter can be evaded by wording it has not seen.

## Not yet evaluated

- Validity, reliability and fairness with human participants.
- Real learning gains.
- Live Claude replies. That path is tested with a stub client because no API key was available during development.
- Voice input across browsers.
