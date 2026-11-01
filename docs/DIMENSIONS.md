# Cognitive dimensions

Generated from `ai4brain/dimensions.py`. Do not edit by hand.

> **Design decision.** The challenge brief refers to "the cognitive dimensions listed in Section 3", but the published PDF contains no such list. We chose these ten because together they cover the skills most often named in cognitive training and in the brief's own framing: focus, memory, speed, reasoning, flexibility, language, spatial thinking, decisions, creativity and self-monitoring. The set lives in one registry and can be changed in minutes if the committee's list differs.

All scores share one model: 3PL item response with a Bayesian grid posterior, reported as a percentage with a 90% credible interval. The percentage is the expected share of a balanced practice set solved. It is not a percentile. Difficulty levels are expert-set design values, not yet calibrated on people.

## Attention

*Holding focus on what matters and ignoring what does not.*

**Definition.** Selective and sustained focus: responding to the relevant signal while distractors compete for it, and holding back an automatic response.

**Tasks.**

- **Arrow focus**: Report the direction of the centre arrow while surrounding arrows point the same or the other way.
- **Press or hold**: Press for every letter except the hold letter. Tests sustained focus and holding back a response.

**Session length.** Up to 16 items per session.

**Scoring.** Two-choice items with a 50% guess floor. Correct responses earn speed-weighted credit: full credit below 60% of the deadline, falling to 60% credit at the deadline. Timeouts count as errors.

**Uncertainty.** Posterior width depends on trial count and on evidence weight. Trials with lost window focus or implausibly fast responses are down-weighted, so the band stays wide.

**Known biases.** Input device and display latency shift response times. Time of day, sleep and noise matter. Practice effects are strong in the first sessions.

## Working memory

*Keeping information in mind while you use it.*

**Definition.** Holding a short sequence in mind and reproducing it, in the same order or transformed.

**Tasks.**

- **Sequence recall**: Watch digits appear one by one, then type them in order.
- **Reverse recall**: Watch digits appear one by one, then type them in reverse order.

**Session length.** Up to 8 items per session.

**Scoring.** Typed recall with no guess floor. Only exact recall earns credit. Digits in the right position are shown as feedback but not scored, because partial credit inflated estimates in evaluation.

**Uncertainty.** Few trials are feasible per session, so the band narrows slowly. Sequence length gives strong item information near the user's limit.

**Known biases.** Familiarity with the digit system, typing speed and rehearsal strategies affect results. Digit tasks favour people schooled in digit-heavy settings.

## Processing speed

*How quickly you can take in simple information and act on it.*

**Definition.** Speed of simple perceptual comparison and of symbol look-up under time pressure.

**Tasks.**

- **Same or different**: Decide quickly whether two strings are identical.
- **Symbol match**: Check whether a symbol-digit pair agrees with the key on screen.

**Session length.** Up to 14 items per session.

**Scoring.** Two-choice items with shrinking deadlines and speed-weighted credit. Tasks are easy on purpose, so response time carries the signal.

**Uncertainty.** Many quick trials give a narrow band fast, but the band does not capture device latency, which is a systematic error.

**Known biases.** Touch screens and slow machines add latency. Age-related speed differences are normal and are not a shortcoming. Reading direction may affect string comparison.

## Logical reasoning

*Finding the rule and following it to a sound conclusion.*

**Definition.** Inducing rules from patterns and deducing what must follow from stated premises.

**Tasks.**

- **Number series**: Find the next number. Rules escalate from constant steps to interleaved series.
- **Must it follow?**: Decide whether a conclusion must follow from premises written with invented words.

**Session length.** Up to 10 items per session.

**Scoring.** Number series use four options (25% guess floor) and syllogisms two options (50%). Untimed apart from a generous limit, so accuracy decides the score.

**Uncertainty.** Each item carries moderate information. A priori difficulty levels are expert-set and not yet calibrated on people, which adds unmodelled error.

**Known biases.** Mathematics schooling helps number series. Invented words reduce, but do not remove, language and test-familiarity effects.

## Cognitive flexibility

*Switching smoothly when the rule changes.*

**Definition.** Reconfiguring behaviour when the active rule changes, measured by accuracy and by the time cost of switching.

**Tasks.**

- **Number rule switch**: A cue says whether to judge a number as odd/even or low/high. The cue changes between trials.
- **Colour or shape**: A cue says whether to sort a figure by its colour or its shape.

**Session length.** Up to 16 items per session.

**Scoring.** Two-choice items with speed-weighted credit. Higher levels raise the share of switch trials and shorten the deadline. Switch cost is reported separately to the coach.

**Uncertainty.** Switch cost is a difference of two noisy means, so it needs many trials. The coach only mentions it when enough switch trials exist.

**Known biases.** Blue and orange are used so the task remains usable with common colour-vision differences. Heavy gaming experience may raise scores.

## Verbal reasoning

*Seeing how words and ideas relate.*

**Definition.** Understanding relations between concepts expressed in words.

**Tasks.**

- **Word analogies**: Complete 'A is to B as C is to ...'.
- **Odd word out**: Pick the word that does not belong with the others.

**Session length.** Up to 10 items per session.

**Scoring.** Four options with a 25% guess floor, drawn from a curated bank tagged by difficulty level.

**Uncertainty.** The bank is finite, so repeated use inflates scores. Repeated items are avoided within a session and flagged across sessions.

**Known biases.** This is the most language-dependent dimension. It measures English vocabulary as well as reasoning and disadvantages non-native speakers. Read scores with that in mind.

## Spatial reasoning

*Turning and flipping shapes in your mind.*

**Definition.** Mentally rotating and mirroring two-dimensional figures.

**Tasks.**

- **Turn the shape**: Pick the option that is the target shape turned, not flipped.
- **Flip the shape**: Pick the left-right mirror image of the target shape.

**Session length.** Up to 10 items per session.

**Scoring.** Four generated options with a 25% guess floor. Grid size and cell count rise with level.

**Uncertainty.** Generated items vary somewhat in real difficulty within a level, adding error the band only partly reflects.

**Known biases.** Experience with drawing, construction games and technical subjects raises scores. Group differences in this kind of task largely track practice opportunity.

## Decision making

*Weighing chances and payoffs instead of following first impressions.*

**Definition.** Comparing options under uncertainty using expected value, ratios and base rates.

**Tasks.**

- **Better bet**: Pick the option worth more on average.
- **Chance check**: Compare chances, from simple ratios up to base-rate reasoning.

**Session length.** Up to 12 items per session.

**Scoring.** Two options with a 50% guess floor. Levels bring the options closer together. Scores reflect expected-value reasoning, not life decisions.

**Uncertainty.** Two-option items carry little information each, so this dimension needs more trials than others.

**Known biases.** Numeracy and statistics training help. Reasonable people may be risk-averse, so the task instructs users to maximise the average and does not judge risk preferences.

## Creative thinking

*Producing varied and unusual ideas.*

**Definition.** Divergent idea generation and finding remote connections between concepts.

**Tasks.**

- **Unusual uses**: List as many unusual uses for an everyday object as you can before time runs out.
- **Word link**: Find one word that connects three others.

**Session length.** Up to 5 items per session.

**Scoring.** Unusual uses: a heuristic combining number of valid ideas, share outside a list of common answers, and variety of ideas. Word link: exact match against accepted answers. Heuristic evidence is deliberately down-weighted.

**Uncertainty.** This is the least reliable dimension. Evidence weight is capped at 0.6 so the band stays wider than for other dimensions, and the interface says so.

**Known biases.** Typing speed, vocabulary and culture shape which answers look unusual. The common-answer lists reflect the authors' perspective.

## Self-monitoring

*Knowing how much to trust your own answers.*

**Definition.** How well your confidence tracks your actual accuracy, and how well you estimate your own performance.

**Tasks.**

- **Confidence rating**: Rate how sure you are after reasoning items. Scored with a proper scoring rule.
- **Session estimate**: After a session, estimate how many items you got right.

**Session length.** Up to 8 items per session.

**Scoring.** Each rated trial earns 1 - 2(c - x)^2, floored at 0, where c is stated confidence and x is the outcome. Session estimates earn 1 - |estimate - actual| / items.

**Uncertainty.** Evidence builds across all reasoning tasks, so it grows steadily, but confidence style differs between cultures and between people.

**Known biases.** Modesty norms and test nerves affect confidence ratings. Very easy or very hard item mixes also shift calibration independently of self-awareness.
