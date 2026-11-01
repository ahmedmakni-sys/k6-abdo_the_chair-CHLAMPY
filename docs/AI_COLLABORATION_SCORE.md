# AI Collaboration Score

The score measures how effectively someone works with an AI, on a scale of 0 to 100. The brief requires a documented formula and proposes weights, describing them as "a design proposal, not validated". This implementation uses those weights unchanged and treats them the same way.

## How it is measured

Self-reports of AI habits are unreliable, so the score comes from behaviour in the **AI collaboration lab**: eight scripted rounds with a simulated assistant.

Some of the assistant's reasoning is deliberately flawed. Because the flaws are planted, catching them is an observation. The rounds are scripted, so the score does not depend on any language model and is reproducible.

In each round the person can commit to an answer first, read the assistant's reasoning, flag steps, ask clarifying questions, send the assistant back to check its work, and choose a final answer. Three rounds also ask a responsible-use question.

## Formula

```
Score = 100 x (0.20 C + 0.25 V + 0.20 I + 0.20 A + 0.15 R)
```

Each share of successes uses Beta(1, 1) smoothing, `(s + 1) / (n + 2)`, so one lucky round cannot produce an extreme value.

| Component | Weight | Definition | Observed as |
|---|---|---|---|
| **C** Clarification | 20% | Share of vague requests where the person asked a relevant question before answering | Questions asked on the ambiguous rounds |
| **V** Critical verification | 25% | Hit rate on flawed steps minus false-alarm rate on sound steps, floored at 0 | Steps flagged against the planted flaws |
| **I** Iteration | 20% | Share of flawed drafts improved through one or two targeted requests that ended in a correct answer | Refinement requests and the final answer |
| **A** Autonomy | 20% | Half own-answer-first rate, half appropriate reliance (right final answer whether the AI was right or wrong) | First answers and final answers |
| **R** Responsible use | 15% | Share of responsible-use questions handled well, counting personal data typed into a question as a failure | Probe choices and a personal-data check |

Design details worth defending:

- **V subtracts false alarms.** Flagging every step earns nothing, so blanket suspicion is not rewarded.
- **I leaves out self-corrected rounds.** Someone who spots the flaw and fixes it unaided has not failed to iterate.
- **A rewards appropriate reliance.** It credits overruling a wrong AI and also accepting a right one, in line with the appropriate-reliance view of trust in automation (Lee and See, 2004).

## Uncertainty and sensitivity

- **Credible interval.** Each component is sampled from its Beta posterior 4,000 times, and the 5th and 95th percentiles of the resulting scores are reported.
- **Weight sensitivity.** The weights are redrawn from a Dirichlet distribution centred on the proposal (concentration 40) with the evidence held fixed. The app shows the resulting range, along with the equal-weights score.

## What it is and is not

It is a mirror for habits. It is not validated, is not a measure of intelligence or character, and should not be used to make decisions about anyone.

The evaluation shows that the score orders simulated behaviour personas as intended (see [EVALUATION.md](EVALUATION.md)). That shows the formula behaves sensibly. It does not show that the score predicts real-world collaboration, which needs a study with people.

## Code

`ai4brain/collab.py`, tested in `tests/test_coach_collab.py`.
