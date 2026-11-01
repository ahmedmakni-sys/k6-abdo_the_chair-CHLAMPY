"""Registry of cognitive dimensions: the single source of truth.

The challenge brief refers to "the cognitive dimensions listed in Section 3" but
the published PDF contains no such list. This registry is therefore a documented
design decision. To change the set, edit DIMENSIONS and TASKS_BY_DIMENSION and add
matching generators in items.py; every other layer reads from here.

docs/DIMENSIONS.md is generated from this file by scripts/gen_docs.py.
"""

DIMENSIONS = {
    "attention": {
        "name": "Attention",
        "plain": "Holding focus on what matters and ignoring what does not.",
        "definition": (
            "Selective and sustained focus: responding to the relevant signal while "
            "distractors compete for it, and holding back an automatic response."
        ),
        "tasks": [
            {"key": "flanker", "name": "Arrow focus",
             "how": "Report the direction of the centre arrow while surrounding arrows point the same or the other way."},
            {"key": "gonogo", "name": "Press or hold",
             "how": "Press for every letter except the hold letter. Tests sustained focus and holding back a response."},
        ],
        "scoring": (
            "Two-choice items with a 50% guess floor. Correct responses earn speed-weighted credit: full credit "
            "below 60% of the deadline, falling to 60% credit at the deadline. Timeouts count as errors."
        ),
        "uncertainty": (
            "Posterior width depends on trial count and on evidence weight. Trials with lost window focus or "
            "implausibly fast responses are down-weighted, so the band stays wide."
        ),
        "biases": (
            "Input device and display latency shift response times. Time of day, sleep and noise matter. "
            "Practice effects are strong in the first sessions."
        ),
    },
    "working_memory": {
        "name": "Working memory",
        "plain": "Keeping information in mind while you use it.",
        "definition": "Holding a short sequence in mind and reproducing it, in the same order or transformed.",
        "tasks": [
            {"key": "digit_span", "name": "Sequence recall",
             "how": "Watch digits appear one by one, then type them in order."},
            {"key": "reverse_span", "name": "Reverse recall",
             "how": "Watch digits appear one by one, then type them in reverse order."},
        ],
        "scoring": (
            "Typed recall with no guess floor. Only exact recall earns credit. Digits in the right position are "
            "shown as feedback but not scored, because partial credit inflated estimates in evaluation."
        ),
        "uncertainty": "Few trials are feasible per session, so the band narrows slowly. Sequence length gives strong item information near the user's limit.",
        "biases": "Familiarity with the digit system, typing speed and rehearsal strategies affect results. Digit tasks favour people schooled in digit-heavy settings.",
    },
    "processing_speed": {
        "name": "Processing speed",
        "plain": "How quickly you can take in simple information and act on it.",
        "definition": "Speed of simple perceptual comparison and of symbol look-up under time pressure.",
        "tasks": [
            {"key": "same_different", "name": "Same or different",
             "how": "Decide quickly whether two strings are identical."},
            {"key": "symbol_match", "name": "Symbol match",
             "how": "Check whether a symbol-digit pair agrees with the key on screen."},
        ],
        "scoring": "Two-choice items with shrinking deadlines and speed-weighted credit. Tasks are easy on purpose, so response time carries the signal.",
        "uncertainty": "Many quick trials give a narrow band fast, but the band does not capture device latency, which is a systematic error.",
        "biases": "Touch screens and slow machines add latency. Age-related speed differences are normal and are not a shortcoming. Reading direction may affect string comparison.",
    },
    "logical_reasoning": {
        "name": "Logical reasoning",
        "plain": "Finding the rule and following it to a sound conclusion.",
        "definition": "Inducing rules from patterns and deducing what must follow from stated premises.",
        "tasks": [
            {"key": "number_series", "name": "Number series",
             "how": "Find the next number. Rules escalate from constant steps to interleaved series."},
            {"key": "syllogism", "name": "Must it follow?",
             "how": "Decide whether a conclusion must follow from premises written with invented words."},
        ],
        "scoring": "Number series use four options (25% guess floor) and syllogisms two options (50%). Untimed apart from a generous limit, so accuracy decides the score.",
        "uncertainty": "Each item carries moderate information. A priori difficulty levels are expert-set and not yet calibrated on people, which adds unmodelled error.",
        "biases": "Mathematics schooling helps number series. Invented words reduce, but do not remove, language and test-familiarity effects.",
    },
    "cognitive_flexibility": {
        "name": "Cognitive flexibility",
        "plain": "Switching smoothly when the rule changes.",
        "definition": "Reconfiguring behaviour when the active rule changes, measured by accuracy and by the time cost of switching.",
        "tasks": [
            {"key": "rule_switch", "name": "Number rule switch",
             "how": "A cue says whether to judge a number as odd/even or low/high. The cue changes between trials."},
            {"key": "colour_shape_shift", "name": "Colour or shape",
             "how": "A cue says whether to sort a figure by its colour or its shape."},
        ],
        "scoring": "Two-choice items with speed-weighted credit. Higher levels raise the share of switch trials and shorten the deadline. Switch cost is reported separately to the coach.",
        "uncertainty": "Switch cost is a difference of two noisy means, so it needs many trials. The coach only mentions it when enough switch trials exist.",
        "biases": "Blue and orange are used so the task remains usable with common colour-vision differences. Heavy gaming experience may raise scores.",
    },
    "verbal_reasoning": {
        "name": "Verbal reasoning",
        "plain": "Seeing how words and ideas relate.",
        "definition": "Understanding relations between concepts expressed in words.",
        "tasks": [
            {"key": "analogy", "name": "Word analogies",
             "how": "Complete 'A is to B as C is to ...'."},
            {"key": "odd_word", "name": "Odd word out",
             "how": "Pick the word that does not belong with the others."},
        ],
        "scoring": "Four options with a 25% guess floor, drawn from a curated bank tagged by difficulty level.",
        "uncertainty": "The bank is finite, so repeated use inflates scores. Repeated items are avoided within a session and flagged across sessions.",
        "biases": "This is the most language-dependent dimension. It measures English vocabulary as well as reasoning and disadvantages non-native speakers. Read scores with that in mind.",
    },
    "spatial_reasoning": {
        "name": "Spatial reasoning",
        "plain": "Turning and flipping shapes in your mind.",
        "definition": "Mentally rotating and mirroring two-dimensional figures.",
        "tasks": [
            {"key": "rotation", "name": "Turn the shape",
             "how": "Pick the option that is the target shape turned, not flipped."},
            {"key": "mirror", "name": "Flip the shape",
             "how": "Pick the left-right mirror image of the target shape."},
        ],
        "scoring": "Four generated options with a 25% guess floor. Grid size and cell count rise with level.",
        "uncertainty": "Generated items vary somewhat in real difficulty within a level, adding error the band only partly reflects.",
        "biases": "Experience with drawing, construction games and technical subjects raises scores. Group differences in this kind of task largely track practice opportunity.",
    },
    "decision_making": {
        "name": "Decision making",
        "plain": "Weighing chances and payoffs instead of following first impressions.",
        "definition": "Comparing options under uncertainty using expected value, ratios and base rates.",
        "tasks": [
            {"key": "expected_value", "name": "Better bet",
             "how": "Pick the option worth more on average."},
            {"key": "base_rate", "name": "Chance check",
             "how": "Compare chances, from simple ratios up to base-rate reasoning."},
        ],
        "scoring": "Two options with a 50% guess floor. Levels bring the options closer together. Scores reflect expected-value reasoning, not life decisions.",
        "uncertainty": "Two-option items carry little information each, so this dimension needs more trials than others.",
        "biases": "Numeracy and statistics training help. Reasonable people may be risk-averse, so the task instructs users to maximise the average and does not judge risk preferences.",
    },
    "creative_thinking": {
        "name": "Creative thinking",
        "plain": "Producing varied and unusual ideas.",
        "definition": "Divergent idea generation and finding remote connections between concepts.",
        "tasks": [
            {"key": "alt_uses", "name": "Unusual uses",
             "how": "List as many unusual uses for an everyday object as you can before time runs out."},
            {"key": "word_link", "name": "Word link",
             "how": "Find one word that connects three others."},
        ],
        "scoring": (
            "Unusual uses: a heuristic combining number of valid ideas, share outside a list of common answers, and "
            "variety of ideas. Word link: exact match against accepted answers. Heuristic evidence is deliberately "
            "down-weighted."
        ),
        "uncertainty": "This is the least reliable dimension. Evidence weight is capped at 0.6 so the band stays wider than for other dimensions, and the interface says so.",
        "biases": "Typing speed, vocabulary and culture shape which answers look unusual. The common-answer lists reflect the authors' perspective.",
    },
    "metacognition": {
        "name": "Self-monitoring",
        "plain": "Knowing how much to trust your own answers.",
        "definition": "How well your confidence tracks your actual accuracy, and how well you estimate your own performance.",
        "tasks": [
            {"key": "confidence_calibration", "name": "Confidence rating",
             "how": "Rate how sure you are after reasoning items. Scored with a proper scoring rule."},
            {"key": "self_estimate", "name": "Session estimate",
             "how": "After a session, estimate how many items you got right."},
        ],
        "scoring": (
            "Each rated trial earns 1 - 2(c - x)^2, floored at 0, where c is stated confidence and x is the outcome. "
            "Session estimates earn 1 - |estimate - actual| / items."
        ),
        "uncertainty": "Evidence builds across all reasoning tasks, so it grows steadily, but confidence style differs between cultures and between people.",
        "biases": "Modesty norms and test nerves affect confidence ratings. Very easy or very hard item mixes also shift calibration independently of self-awareness.",
    },
}

DIMENSION_KEYS = list(DIMENSIONS)

# The confidence and self-estimate tasks generate evidence for metacognition but
# are not stand-alone generators, so the mapping below excludes them.
TASKS_BY_DIMENSION = {
    k: [t["key"] for t in v["tasks"]] for k, v in DIMENSIONS.items() if k != "metacognition"
}

# Practising self-monitoring draws reasoning items from these tasks with a mandatory confidence rating.
METACOGNITION_POOL = ["number_series", "analogy", "rotation", "expected_value", "syllogism"]


def dimension_for_task(task):
    for dim, tasks in TASKS_BY_DIMENSION.items():
        if task in tasks:
            return dim
    raise KeyError(task)
