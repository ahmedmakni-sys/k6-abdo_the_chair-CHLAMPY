"""Item generators and scoring for every task.

Every generator takes (level, rng, ctx) and returns a dict with:
  kind       renderer used by the web app (choice, go_nogo, recall, mcq, free_text)
  prompt     text shown to the user
  payload    data needed to render the item (never contains the answer)
  answer     correct response, kept on the server
  deadline_ms  time limit; timeouts score as errors on speeded tasks

Levels run 1 to 10. Difficulty parameters are expert-set a-priori values, not
empirically calibrated ones, and are documented as such.
"""

import random
import re

from . import estimator as est
from .dimensions import TASKS_BY_DIMENSION, dimension_for_task

# Task-level model parameters: discrimination a, guess floor c, speeded flag, reliability cap.
TASK_PARAMS = {
    "flanker": dict(a=1.1, c=0.5, speeded=True, cap=1.0),
    "gonogo": dict(a=1.0, c=0.5, speeded=True, cap=1.0),
    "digit_span": dict(a=1.4, c=0.0, speeded=False, cap=1.0),
    "reverse_span": dict(a=1.4, c=0.0, speeded=False, cap=1.0),
    "same_different": dict(a=1.1, c=0.5, speeded=True, cap=1.0),
    "symbol_match": dict(a=1.1, c=0.5, speeded=True, cap=1.0),
    "number_series": dict(a=1.3, c=0.25, speeded=False, cap=1.0),
    "syllogism": dict(a=1.1, c=0.5, speeded=False, cap=1.0),
    "rule_switch": dict(a=1.1, c=0.5, speeded=True, cap=1.0),
    "colour_shape_shift": dict(a=1.1, c=0.5, speeded=True, cap=1.0),
    "analogy": dict(a=1.2, c=0.25, speeded=False, cap=1.0),
    "odd_word": dict(a=1.1, c=0.25, speeded=False, cap=1.0),
    "rotation": dict(a=1.2, c=0.25, speeded=False, cap=1.0),
    "mirror": dict(a=1.2, c=0.25, speeded=False, cap=1.0),
    "expected_value": dict(a=1.0, c=0.5, speeded=False, cap=1.0),
    "base_rate": dict(a=1.0, c=0.5, speeded=False, cap=1.0),
    "alt_uses": dict(a=0.9, c=0.0, speeded=False, cap=0.6),
    "word_link": dict(a=1.1, c=0.0, speeded=False, cap=0.6),
}

# Below this response time an answer cannot plausibly reflect reading the item.
RT_FLOOR_MS = {
    "choice": 150, "go_nogo": 120, "recall": 300, "mcq": 800, "free_text": 3000,
}

INSTRUCTIONS = {
    "flanker": "Press the arrow key that matches the centre arrow only. Ignore the arrows around it.",
    "gonogo": "Press Space for every letter, unless it is the hold letter shown on screen. For that letter, do nothing.",
    "digit_span": "Watch the digits, then type them in the same order.",
    "reverse_span": "Watch the digits, then type them in reverse order.",
    "same_different": "Are the two strings identical? Left arrow for same, right arrow for different.",
    "symbol_match": "Does the pair below agree with the key? Left arrow for yes, right arrow for no.",
    "number_series": "Find the rule and choose the next number.",
    "syllogism": "Treat the statements as true, even though the words are invented. Must the conclusion follow?",
    "rule_switch": "Follow the cue: it tells you which question to answer about the number. The cue can change at any time.",
    "colour_shape_shift": "Follow the cue: sort the figure by its colour or by its shape. The cue can change at any time.",
    "analogy": "Choose the word that completes the relationship.",
    "odd_word": "Choose the word that does not belong with the other three.",
    "rotation": "Choose the option that is the target turned around. A flipped shape does not count.",
    "mirror": "Choose the option that is the target flipped left-to-right.",
    "expected_value": "Imagine playing many times. Which option wins more points on average?",
    "base_rate": "Work out which is more likely. A rough calculation is fine.",
    "alt_uses": "List as many unusual uses as you can, one per line. Variety counts more than quantity.",
    "word_link": "Type one word that connects all three words.",
}


def _lerp(level, low, high):
    return low + (high - low) * (level - 1) / (est.LEVELS - 1)


# ---- attention ---------------------------------------------------------------

def gen_flanker(level, rng, ctx):
    side = 2 if level <= 4 else 3 if level <= 7 else 4
    incongruent = rng.random() < _lerp(level, 0.2, 0.85)
    centre = rng.choice(["left", "right"])
    other = "right" if centre == "left" else "left"
    flank = other if incongruent else centre
    return dict(
        kind="choice",
        prompt="Which way does the centre arrow point?",
        payload=dict(
            stimulus_type="arrows",
            arrows=[flank] * side + [centre] + [flank] * side,
            choices=[dict(key="left", label="Left"), dict(key="right", label="Right")],
        ),
        answer=centre,
        deadline_ms=int(_lerp(level, 2400, 800)),
        meta=dict(incongruent=incongruent),
    )


def gen_gonogo(level, rng, ctx):
    hold = "X" if level <= 4 else "K" if level <= 7 else "Y"
    # Similar-looking letters make holding back harder at higher levels.
    lures = {"X": "BMPTRS", "K": "XRHBMT", "Y": "VXKTUW"}[hold]
    is_hold = rng.random() < _lerp(level, 0.2, 0.45)
    letter = hold if is_hold else rng.choice(lures)
    return dict(
        kind="go_nogo",
        prompt=f"Press Space unless you see {hold}",
        payload=dict(letter=letter, hold=hold),
        answer="hold" if is_hold else "go",
        deadline_ms=int(_lerp(level, 1500, 550)),
        meta=dict(hold_trial=is_hold),
    )


# ---- working memory ----------------------------------------------------------

def _digits(n, rng):
    out = []
    while len(out) < n:
        d = rng.randint(0, 9)
        if not out or d != out[-1]:
            out.append(d)
    return out


def gen_digit_span(level, rng, ctx):
    n = level + 2
    seq = _digits(n, rng)
    return dict(
        kind="recall",
        prompt="Type the digits in the same order",
        payload=dict(sequence=seq, show_ms=850, length=n),
        answer="".join(map(str, seq)),
        deadline_ms=25000,
    )


def gen_reverse_span(level, rng, ctx):
    n = level + 1
    seq = _digits(n, rng)
    return dict(
        kind="recall",
        prompt="Type the digits in reverse order",
        payload=dict(sequence=seq, show_ms=850, length=n),
        answer="".join(map(str, reversed(seq))),
        deadline_ms=25000,
    )


# ---- processing speed --------------------------------------------------------

SIMILAR = {"O": "Q", "Q": "O", "E": "F", "F": "E", "C": "G", "G": "C", "M": "N", "N": "M",
           "P": "R", "R": "P", "U": "V", "V": "U", "3": "8", "8": "3", "5": "6", "6": "5"}
STRING_ALPHABET = "BCDEFGHJKMNPQRSTUVWXYZ2345678"


def gen_same_different(level, rng, ctx):
    n = level + 3
    a = [rng.choice(STRING_ALPHABET) for _ in range(n)]
    b = list(a)
    same = rng.random() < 0.5
    if not same:
        i = rng.randrange(n)
        if level >= 5 and a[i] in SIMILAR:
            b[i] = SIMILAR[a[i]]
        else:
            b[i] = rng.choice([c for c in STRING_ALPHABET if c != a[i]])
    return dict(
        kind="choice",
        prompt="Are these identical?",
        payload=dict(
            stimulus_type="strings", left="".join(a), right="".join(b),
            choices=[dict(key="same", label="Same"), dict(key="different", label="Different")],
        ),
        answer="same" if same else "different",
        deadline_ms=int(_lerp(level, 6000, 1900)),
    )


SYMBOLS = ["◆", "▲", "●", "■", "★", "✚", "▼", "◐", "⬟"]


def gen_symbol_match(level, rng, ctx):
    n = min(3 + (level - 1) * 2 // 3, len(SYMBOLS))
    syms = rng.sample(SYMBOLS, n)
    digits = rng.sample(range(1, 10), n)
    key = list(zip(syms, digits))
    i = rng.randrange(n)
    match = rng.random() < 0.5
    shown = digits[i] if match else rng.choice([d for d in range(1, 10) if d != digits[i]])
    return dict(
        kind="choice",
        prompt="Does this pair agree with the key?",
        payload=dict(
            stimulus_type="symbol_key", key=[dict(s=s, d=d) for s, d in key], probe=dict(s=syms[i], d=shown),
            choices=[dict(key="yes", label="Agrees"), dict(key="no", label="Disagrees")],
        ),
        answer="yes" if match else "no",
        deadline_ms=int(_lerp(level, 5500, 1900)),
    )


# ---- logical reasoning -------------------------------------------------------

def _series(level, rng):
    """Return (visible terms, next term)."""
    if level <= 2:
        start, step = rng.randint(1, 20), rng.randint(2, 6) * level
        s = [start + i * step for i in range(6)]
    elif level <= 4:
        if rng.random() < 0.5:
            start, step = rng.randint(50, 120), -rng.randint(3, 12)
            s = [start + i * step for i in range(6)]
        else:
            start, r = rng.randint(1, 5), rng.choice([2, 3])
            s = [start * r ** i for i in range(6)]
    elif level <= 6:
        start, u, v = rng.randint(1, 20), rng.randint(2, 9), rng.randint(2, 9)
        s = [start]
        for i in range(6):
            s.append(s[-1] + (u if i % 2 == 0 else -v))
    elif level <= 8:
        start, d, dd = rng.randint(1, 15), rng.randint(1, 5), rng.randint(1, 4)
        s = [start]
        for i in range(6):
            s.append(s[-1] + d + i * dd)
    else:
        a0, a1 = rng.randint(1, 9), rng.randint(2, 5)
        b0, r = rng.randint(1, 4), rng.choice([2, 3])
        s = []
        for i in range(8):
            s.append(a0 + (i // 2) * a1 if i % 2 == 0 else b0 * r ** (i // 2))
    return s[:-1], s[-1]


def gen_number_series(level, rng, ctx):
    shown, ans = _series(level, rng)
    gap = abs(shown[-1] - shown[-2]) or 1
    options = {ans}
    candidates = [ans + gap, ans - gap, ans + 1, ans - 1, ans + 2, ans - 2, shown[-1] + gap, ans * 2]
    rng.shuffle(candidates)
    for cand in candidates:
        if len(options) == 4:
            break
        options.add(cand)
    delta = 3
    while len(options) < 4:
        options.add(ans + delta)
        delta += 1
    options = [str(o) for o in options]
    rng.shuffle(options)
    return dict(
        kind="mcq",
        prompt=", ".join(map(str, shown)) + ", ?",
        payload=dict(options=options, big_prompt=True),
        answer=str(ans),
        deadline_ms=60000,
    )


NONSENSE = ["blicks", "trems", "zaps", "florps", "wugs", "daxes", "mibs", "tovs", "kems", "rulps", "gorns", "vems"]


def gen_syllogism(level, rng, ctx):
    n_terms = 3 if level <= 3 else 4 if level <= 7 else 5
    terms = rng.sample(NONSENSE, n_terms)
    premises = [f"All {terms[i]} are {terms[i + 1]}." for i in range(n_terms - 1)]
    first, last = terms[0], terms[-1]
    use_negative = level >= 4 and rng.random() < 0.5
    use_some = level >= 7 and rng.random() < 0.6
    truth = rng.random() < 0.5
    if use_some:
        premises[0] = f"Some {terms[0]} are {terms[1]}."
        conclusion = f"Some {first} are {last}." if truth else f"All {first} are {last}."
    elif use_negative:
        premises[-1] = f"No {terms[-2]} are {terms[-1]}."
        conclusion = f"No {first} are {last}." if truth else f"Some {first} are {last}."
    else:
        conclusion = f"All {first} are {last}." if truth else f"All {last} are {first}."
    rng.shuffle(premises)
    return dict(
        kind="mcq",
        prompt=" ".join(premises) + f" Conclusion: {conclusion}",
        payload=dict(options=["It must follow", "It does not have to follow"], fixed_order=True),
        answer="It must follow" if truth else "It does not have to follow",
        deadline_ms=60000,
    )


# ---- cognitive flexibility ---------------------------------------------------

def gen_rule_switch(level, rng, ctx):
    prev = ctx.get("prev_rule")
    p_switch = _lerp(level, 0.2, 0.8)
    if prev is None:
        rule = rng.choice(["parity", "size"])
    else:
        rule = ("size" if prev == "parity" else "parity") if rng.random() < p_switch else prev
    n = rng.choice([1, 2, 3, 4, 6, 7, 8, 9])
    if rule == "parity":
        cue, choices = "Odd or even?", [dict(key="odd", label="Odd"), dict(key="even", label="Even")]
        ans = "odd" if n % 2 else "even"
    else:
        cue, choices = "Below or above 5?", [dict(key="low", label="Below 5"), dict(key="high", label="Above 5")]
        ans = "low" if n < 5 else "high"
    return dict(
        kind="choice",
        prompt=cue,
        payload=dict(stimulus_type="number", number=n, cue=cue, choices=choices),
        answer=ans,
        deadline_ms=int(_lerp(level, 3500, 1100)),
        meta=dict(rule=rule, is_switch=prev is not None and rule != prev),
        ctx_update=dict(prev_rule=rule),
    )


def gen_colour_shape_shift(level, rng, ctx):
    prev = ctx.get("prev_rule")
    p_switch = _lerp(level, 0.2, 0.8)
    if prev is None:
        rule = rng.choice(["colour", "shape"])
    else:
        rule = ("shape" if prev == "colour" else "colour") if rng.random() < p_switch else prev
    colour, shape = rng.choice(["blue", "orange"]), rng.choice(["circle", "square"])
    if rule == "colour":
        cue, choices = "Colour?", [dict(key="blue", label="Blue"), dict(key="orange", label="Orange")]
        ans = colour
    else:
        cue, choices = "Shape?", [dict(key="circle", label="Circle"), dict(key="square", label="Square")]
        ans = shape
    return dict(
        kind="choice",
        prompt=cue,
        payload=dict(stimulus_type="figure", colour=colour, shape=shape, cue=cue, choices=choices),
        answer=ans,
        deadline_ms=int(_lerp(level, 3500, 1100)),
        meta=dict(rule=rule, is_switch=prev is not None and rule != prev),
        ctx_update=dict(prev_rule=rule),
    )


# ---- verbal reasoning (curated banks, (level, stem, answer, distractors)) -----

ANALOGIES = [
    (1, "Hot is to cold as up is to", "down", ["high", "warm", "over"]),
    (1, "Puppy is to dog as kitten is to", "cat", ["pet", "mouse", "fur"]),
    (1, "Bird is to nest as bee is to", "hive", ["honey", "flower", "wing"]),
    (2, "Hand is to glove as foot is to", "sock", ["toe", "walk", "leg"]),
    (2, "Pen is to write as knife is to", "cut", ["sharp", "fork", "steel"]),
    (2, "Day is to night as summer is to", "winter", ["sun", "hot", "spring"]),
    (3, "Doctor is to hospital as teacher is to", "school", ["book", "student", "lesson"]),
    (3, "Page is to book as branch is to", "tree", ["leaf", "wood", "root"]),
    (3, "Painter is to brush as writer is to", "pen", ["book", "word", "paper"]),
    (4, "Thermometer is to temperature as clock is to", "time", ["hour", "wall", "alarm"]),
    (4, "Seed is to plant as egg is to", "chick", ["shell", "nest", "yolk"]),
    (4, "Island is to water as oasis is to", "desert", ["palm", "camel", "well"]),
    (5, "Author is to novel as composer is to", "symphony", ["piano", "orchestra", "melody"]),
    (5, "Hungry is to food as thirsty is to", "water", ["dry", "drink", "glass"]),
    (5, "Fragile is to break as flammable is to", "burn", ["fire", "gas", "smoke"]),
    (6, "Drought is to rain as famine is to", "food", ["hunger", "crop", "winter"]),
    (6, "Chapter is to novel as scene is to", "play", ["actor", "stage", "script"]),
    (6, "Compass is to direction as scale is to", "weight", ["fish", "music", "balance"]),
    (7, "Prologue is to epilogue as overture is to", "finale", ["opera", "curtain", "aria"]),
    (7, "Candid is to frank as obscure is to", "unclear", ["hidden", "dark", "rare"]),
    (7, "Parched is to dry as famished is to", "hungry", ["thin", "food", "weak"]),
    (8, "Ephemeral is to lasting as candid is to", "evasive", ["honest", "open", "brief"]),
    (8, "Cartographer is to map as lexicographer is to", "dictionary", ["language", "word", "atlas"]),
    (8, "Frugal is to spend as taciturn is to", "speak", ["quiet", "listen", "save"]),
    (9, "Prescient is to foresight as magnanimous is to", "generosity", ["wealth", "pride", "courage"]),
    (9, "Laconic is to words as austere is to", "ornament", ["discipline", "severe", "poverty"]),
    (9, "Sapling is to oak as fledgling is to", "eagle", ["nest", "feather", "flight"]),
    (10, "Obdurate is to persuade as intractable is to", "control", ["stubborn", "argue", "solve"]),
    (10, "Panacea is to ills as skeleton key is to", "locks", ["doors", "bones", "metal"]),
    (10, "Sycophant is to flattery as iconoclast is to", "dissent", ["images", "praise", "faith"]),
]

ODD_WORDS = [
    (1, ["apple", "pear", "plum"], "chair"),
    (1, ["red", "blue", "green"], "loud"),
    (2, ["run", "walk", "jog"], "sleep"),
    (2, ["spoon", "fork", "knife"], "pillow"),
    (3, ["violin", "cello", "harp"], "trumpet"),
    (3, ["oak", "pine", "birch"], "daisy"),
    (4, ["whisper", "murmur", "mumble"], "shout"),
    (4, ["inch", "metre", "mile"], "pound"),
    (5, ["brave", "bold", "daring"], "cautious"),
    (5, ["copper", "iron", "zinc"], "quartz"),
    (6, ["novel", "essay", "memoir"], "sculpture"),
    (6, ["delay", "postpone", "defer"], "hasten"),
    (7, ["lucid", "clear", "plain"], "murky"),
    (7, ["triangle", "square", "hexagon"], "circle"),
    (8, ["abundant", "plentiful", "ample"], "scarce"),
    (8, ["mercury", "venus", "saturn"], "sirius"),
    (9, ["benign", "harmless", "innocuous"], "noxious"),
    (9, ["sonnet", "haiku", "limerick"], "fable"),
    (10, ["garrulous", "loquacious", "voluble"], "reticent"),
    (10, ["pragmatic", "practical", "utilitarian"], "quixotic"),
]


def _from_bank(bank, level, rng, ctx):
    """Pick an item at the nearest available level, avoiding repeats in the session."""
    used = set(ctx.get("used_items", []))
    ordered = sorted(range(len(bank)), key=lambda i: (abs(bank[i][0] - level), rng.random()))
    for i in ordered:
        if i not in used:
            return i, bank[i]
    return ordered[0], bank[ordered[0]]


def gen_analogy(level, rng, ctx):
    i, (lvl, stem, ans, wrong) = _from_bank(ANALOGIES, level, rng, ctx)
    options = [ans] + wrong
    rng.shuffle(options)
    return dict(
        kind="mcq", prompt=stem + " ...", payload=dict(options=options), answer=ans,
        deadline_ms=60000, level_override=lvl,
        ctx_update=dict(used_items=ctx.get("used_items", []) + [i]),
    )


def gen_odd_word(level, rng, ctx):
    i, (lvl, group, odd) = _from_bank(ODD_WORDS, level, rng, ctx)
    options = group + [odd]
    rng.shuffle(options)
    return dict(
        kind="mcq", prompt="Which word does not belong?", payload=dict(options=options), answer=odd,
        deadline_ms=60000, level_override=lvl,
        ctx_update=dict(used_items=ctx.get("used_items", []) + [i]),
    )


# ---- spatial reasoning -------------------------------------------------------

def _grow_shape(n_cells, size, rng):
    cells = {(rng.randrange(size), rng.randrange(size))}
    while len(cells) < n_cells:
        r, c = rng.choice(sorted(cells))
        dr, dc = rng.choice([(0, 1), (1, 0), (0, -1), (-1, 0)])
        nr, nc = r + dr, c + dc
        if 0 <= nr < size and 0 <= nc < size:
            cells.add((nr, nc))
    return cells


def _rotate(cells, size):
    return {(c, size - 1 - r) for r, c in cells}


def _flip(cells, size):
    return {(r, size - 1 - c) for r, c in cells}


def _normal(cells):
    """Position-independent form, so comparisons ignore where a shape sits in its grid."""
    min_r = min(r for r, _ in cells)
    min_c = min(c for _, c in cells)
    return frozenset((r - min_r, c - min_c) for r, c in cells)


def _rotations(cells, size):
    out, cur = [], cells
    for _ in range(4):
        out.append(cur)
        cur = _rotate(cur, size)
    return out


def _chiral_shape(n_cells, size, rng):
    """A shape whose mirror image cannot be reached by turning it."""
    while True:
        cells = _grow_shape(n_cells, size, rng)
        rot_forms = {_normal(r) for r in _rotations(cells, size)}
        if _normal(_flip(cells, size)) not in rot_forms and len(rot_forms) == 4:
            return cells


def _tweak(cells, size, rng):
    """Move one cell, producing a near-identical but different shape."""
    cells = set(cells)
    for _ in range(100):
        out = rng.choice(sorted(cells))
        rest = cells - {out}
        spots = {(r + dr, c + dc) for r, c in rest for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]}
        spots = {(r, c) for r, c in spots if 0 <= r < size and 0 <= c < size} - cells
        if spots:
            return rest | {rng.choice(sorted(spots))}
    return cells


def _grid(cells):
    return sorted([list(x) for x in cells])


def _distinct_options(correct, pool, rng):
    """Up to 3 distractors that differ from the correct option and from each other."""
    seen = {_normal(correct)}
    picked = []
    for cand in pool:
        form = _normal(cand)
        if form not in seen:
            seen.add(form)
            picked.append(cand)
        if len(picked) == 3:
            break
    return picked


def gen_rotation(level, rng, ctx):
    size = 3 if level <= 3 else 4 if level <= 7 else 5
    n_cells = 4 + (level - 1) * 5 // 9
    target = _chiral_shape(n_cells, size, rng)
    rots = _rotations(target, size)
    correct = rots[rng.choice([1, 2, 3])]
    flipped = _flip(target, size)
    pool = [_rotate(flipped, size), _rotate(_rotate(flipped, size), size), flipped]
    rng.shuffle(pool)
    pool += [_tweak(target, size, rng) for _ in range(6)]
    distractors = _distinct_options(correct, pool, rng)
    options = [dict(id=str(i), cells=_grid(c)) for i, c in enumerate([correct] + distractors)]
    answer = "0"
    rng.shuffle(options)
    relabel = {o["id"]: str(i) for i, o in enumerate(options)}
    for o in options:
        o["id"] = relabel[o["id"]]
    return dict(
        kind="mcq",
        prompt="Which option is the target turned around?",
        payload=dict(grid_size=size, target=_grid(target), grid_options=options, options=[o["id"] for o in options]),
        answer=relabel[answer],
        deadline_ms=60000,
    )


def gen_mirror(level, rng, ctx):
    size = 3 if level <= 3 else 4 if level <= 7 else 5
    n_cells = 4 + (level - 1) * 5 // 9
    target = _chiral_shape(n_cells, size, rng)
    correct = _flip(target, size)
    pool = [_rotate(target, size), _rotate(_rotate(target, size), size), target]
    rng.shuffle(pool)
    pool += [_tweak(correct, size, rng) for _ in range(6)]
    distractors = _distinct_options(correct, pool, rng)
    options = [dict(id=str(i), cells=_grid(c)) for i, c in enumerate([correct] + distractors)]
    rng.shuffle(options)
    relabel = {o["id"]: str(i) for i, o in enumerate(options)}
    for o in options:
        o["id"] = relabel[o["id"]]
    return dict(
        kind="mcq",
        prompt="Which option is the target flipped left-to-right?",
        payload=dict(grid_size=size, target=_grid(target), grid_options=options, options=[o["id"] for o in options]),
        answer=relabel["0"],
        deadline_ms=60000,
    )


# ---- decision making ---------------------------------------------------------

def gen_expected_value(level, rng, ctx):
    # The options' averages differ by this ratio: obvious at low levels, close at high ones.
    ratio = _lerp(level, 1.8, 1.05)
    for _ in range(200):
        pa, pb = rng.randrange(10, 95, 5), rng.randrange(10, 95, 5)
        va = rng.randrange(10, 200, 5 if level < 6 else 1)
        vb = rng.randrange(10, 200, 5 if level < 6 else 1)
        ea, eb = pa * va / 100.0, pb * vb / 100.0
        if min(ea, eb) <= 0:
            continue
        r = max(ea, eb) / min(ea, eb)
        # Keep the higher-probability option from always being right.
        if ratio * 0.97 <= r <= ratio * 1.1 and pa != pb and va != vb:
            break
    else:
        pa, va, pb, vb = 80, 50, 50, 40
        ea, eb = 40.0, 20.0
    best = "A" if ea > eb else "B"
    return dict(
        kind="mcq",
        prompt="Which option wins more points on average?",
        payload=dict(
            options=["A", "B"], fixed_order=True,
            option_labels=dict(A=f"{pa}% chance of {va} points", B=f"{pb}% chance of {vb} points"),
        ),
        answer=best,
        deadline_ms=60000,
    )


BASE_RATE_CONTEXTS = [
    ("parcels", "damaged", "A scanner"),
    ("emails", "spam", "A filter"),
    ("orchard apples", "bruised", "A sorting machine"),
    ("tickets", "fake", "A reader"),
]


def gen_base_rate(level, rng, ctx):
    if level <= 4:
        ratio = _lerp(level, 2.0, 1.2)
        for _ in range(200):
            da, db = rng.choice([10, 20, 40, 50, 100]), rng.choice([10, 20, 40, 50, 100, 200])
            ra, rb = rng.randint(1, da - 1), rng.randint(1, db - 1)
            a, b = ra / da, rb / db
            if min(a, b) > 0 and ratio * 0.95 <= max(a, b) / min(a, b) <= ratio * 1.1 and da != db:
                break
        else:
            ra, da, rb, db = 3, 10, 10, 100
            a, b = 0.3, 0.1
        return dict(
            kind="mcq",
            prompt=f"Bag A holds {ra} red marbles out of {da}. Bag B holds {rb} red marbles out of {db}. You draw one marble without looking. Which bag gives the better chance of red?",
            payload=dict(options=["Bag A", "Bag B"], fixed_order=True),
            answer="Bag A" if a > b else "Bag B",
            deadline_ms=60000,
        )
    # Base-rate reasoning. Margin around 50% shrinks as the level rises.
    margin = _lerp(level, 0.3, 0.08)
    for _ in range(400):
        base = rng.choice([1, 2, 5, 10, 20, 30, 40])
        hit = rng.choice([70, 80, 90, 95])
        false_alarm = rng.choice([1, 2, 5, 10, 20, 30])
        tp, fp = base * hit, (100 - base) * false_alarm
        post = tp / (tp + fp)
        if margin * 0.7 <= abs(post - 0.5) <= margin * 1.4:
            break
    else:
        base, hit, false_alarm, post = 10, 90, 20, 1 / 3
    noun, attr, tool = rng.choice(BASE_RATE_CONTEXTS)
    return dict(
        kind="mcq",
        prompt=(
            f"{base}% of {noun} are {attr}. {tool} flags {hit}% of the {attr} ones, and also wrongly flags "
            f"{false_alarm}% of the others. One has just been flagged. Is it more likely to be {attr} or not?"
        ),
        payload=dict(options=[f"More likely {attr}", f"More likely not {attr}"], fixed_order=True),
        answer=f"More likely {attr}" if post > 0.5 else f"More likely not {attr}",
        deadline_ms=90000,
    )


# ---- creative thinking -------------------------------------------------------

ALT_USES_OBJECTS = {
    "brick": {"build", "wall", "house", "doorstop", "door", "weight", "paperweight", "throw", "weapon", "step", "break"},
    "paperclip": {"hold", "paper", "bookmark", "pick", "lock", "reset", "pin", "hook", "clip", "unlock"},
    "newspaper": {"read", "wrap", "fire", "clean", "window", "hat", "swat", "fly", "pet", "pack", "boat"},
    "bucket": {"water", "carry", "hat", "sit", "stool", "drum", "wash", "plant", "mop", "paint"},
    "spoon": {"eat", "stir", "mirror", "dig", "scoop", "measure", "music", "catapult", "feed"},
    "shoe": {"wear", "walk", "door", "hammer", "plant", "pot", "throw", "hit", "doorstop", "flowerpot"},
    "towel": {"dry", "clean", "wash", "cape", "wrap", "whip", "blanket", "mop", "sit", "pillow"},
    "bottle": {"drink", "water", "vase", "flower", "funnel", "roll", "rolling", "message", "lamp", "piggy", "bank"},
}

WORD_LINKS = [
    (1, ["apple", "pine", "palm"], {"tree"}),
    (1, ["fire", "green", "white"], {"house"}),
    (2, ["cottage", "swiss", "cake"], {"cheese"}),
    (2, ["sun", "moon", "star"], {"light"}),
    (3, ["ball", "print", "step"], {"foot"}),
    (3, ["rain", "test", "stomach"], {"acid"}),
    (4, ["blood", "music", "cheese"], {"blue"}),
    (4, ["falling", "actor", "dust"], {"star"}),
    (5, ["duck", "fold", "dollar"], {"bill"}),
    (5, ["dream", "break", "light"], {"day"}),
    (6, ["sense", "courtesy", "place"], {"common"}),
    (6, ["night", "wrist", "stop"], {"watch"}),
    (7, ["pure", "blue", "fall"], {"water"}),
    (7, ["board", "magic", "death"], {"black"}),
    (8, ["safety", "cushion", "point"], {"pin"}),
    (8, ["soap", "shoe", "tissue"], {"box"}),
    (9, ["hound", "pressure", "shot"], {"blood"}),
    (9, ["pie", "luck", "belly"], {"pot"}),
    (10, ["measure", "worm", "video"], {"tape"}),
    (10, ["boot", "summer", "ground"], {"camp"}),
]

_STOP = {"a", "an", "the", "to", "for", "as", "of", "with", "on", "in", "it", "use", "using", "make", "making", "and", "or", "your"}


def gen_alt_uses(level, rng, ctx):
    used = ctx.get("used_objects", [])
    choices = [o for o in ALT_USES_OBJECTS if o not in used] or list(ALT_USES_OBJECTS)
    obj = rng.choice(choices)
    seconds = int(_lerp(level, 90, 45))
    return dict(
        kind="free_text",
        prompt=f"Unusual uses for a {obj}",
        payload=dict(object=obj, seconds=seconds, multiline=True),
        answer=obj,
        deadline_ms=seconds * 1000,
        ctx_update=dict(used_objects=used + [obj]),
    )


def gen_word_link(level, rng, ctx):
    i, (lvl, words, accepted) = _from_bank(WORD_LINKS, level, rng, ctx)
    return dict(
        kind="free_text",
        prompt=" + ".join(words) + " = ?",
        payload=dict(seconds=45, multiline=False, words=words),
        answer=sorted(accepted),
        deadline_ms=45000,
        level_override=lvl,
        ctx_update=dict(used_items=ctx.get("used_items", []) + [i]),
    )


GENERATORS = {
    "flanker": gen_flanker, "gonogo": gen_gonogo,
    "digit_span": gen_digit_span, "reverse_span": gen_reverse_span,
    "same_different": gen_same_different, "symbol_match": gen_symbol_match,
    "number_series": gen_number_series, "syllogism": gen_syllogism,
    "rule_switch": gen_rule_switch, "colour_shape_shift": gen_colour_shape_shift,
    "analogy": gen_analogy, "odd_word": gen_odd_word,
    "rotation": gen_rotation, "mirror": gen_mirror,
    "expected_value": gen_expected_value, "base_rate": gen_base_rate,
    "alt_uses": gen_alt_uses, "word_link": gen_word_link,
}

for _dim, _tasks in TASKS_BY_DIMENSION.items():
    for _t in _tasks:
        assert _t in GENERATORS and _t in TASK_PARAMS, _t


def generate(task, level, rng=None, ctx=None):
    rng = rng or random.Random()
    ctx = ctx or {}
    level = max(1, min(est.LEVELS, int(level)))
    item = GENERATORS[task](level, rng, ctx)
    actual = item.pop("level_override", level)
    params = TASK_PARAMS[task]
    item.update(
        task=task,
        dimension=dimension_for_task(task),
        level=actual,
        b=est.level_to_b(actual),
        a=params["a"],
        c=params["c"],
        speeded=params["speeded"],
    )
    item.setdefault("meta", {})
    item["instructions"] = INSTRUCTIONS[task]
    return item


# ---- scoring -----------------------------------------------------------------

def _speed_credit(rt_ms, deadline_ms):
    """Full credit below 60% of the deadline, falling linearly to 60% credit at it."""
    if not rt_ms or not deadline_ms:
        return 1.0
    frac = (rt_ms / deadline_ms - 0.6) / 0.4
    return 1.0 - 0.4 * max(0.0, min(1.0, frac))


def _clean_ideas(text):
    raw = re.split(r"[\n,;]+", (text or "").lower())
    seen, ideas = set(), []
    for part in raw:
        words = re.findall(r"[a-zà-ÿ']+", part)
        content = [w for w in words if w not in _STOP]
        # Reject fragments and keyboard mashing: a real idea has a word with a vowel.
        if not content or not any(re.search(r"[aeiouy]", w) and len(set(w)) >= 3 for w in content):
            continue
        key = " ".join(sorted(set(content)))
        if key in seen:
            continue
        seen.add(key)
        ideas.append(content)
    return ideas


def score_alt_uses(item, text):
    """Heuristic creative score. Low reliability, reflected in the evidence cap."""
    ideas = _clean_ideas(text)
    common = ALT_USES_OBJECTS.get(item["answer"], set())
    if not ideas:
        return dict(y=0.0, correct=False, ideas=0, unusual=0, variety=0.0)
    unusual = sum(1 for idea in ideas if not (set(idea) & common))
    verbs = {idea[0] for idea in ideas}
    target = 3 + item["level"] * 0.7
    fluency = min(1.0, len(ideas) / target)
    originality = unusual / len(ideas)
    variety = len(verbs) / len(ideas)
    y = 0.45 * fluency + 0.35 * originality + 0.20 * variety
    return dict(y=round(y, 3), correct=y >= 0.5, ideas=len(ideas), unusual=unusual, variety=round(variety, 2))


def score_response(item, response, rt_ms):
    """Return outcome y, correct flag and extra detail for a server-held item."""
    task = item["task"]
    timed_out = response is None or response == ""
    detail = {}
    if task == "gonogo":
        pressed = response == "go"
        correct = pressed == (item["answer"] == "go")
        y = 1.0 if correct else 0.0
        if correct and pressed:
            y *= _speed_credit(rt_ms, item["deadline_ms"])
        return dict(correct=correct, y=y, timed_out=not pressed and item["answer"] == "go", detail=detail)
    if timed_out and task != "alt_uses":
        return dict(correct=False, y=0.0, timed_out=True, detail=detail)
    if task in ("digit_span", "reverse_span"):
        typed = re.sub(r"\D", "", str(response))
        ans = item["answer"]
        correct = typed == ans
        # Partial matches are reported for feedback only. Scoring them inflated estimates in evaluation.
        detail = dict(positions_right=sum(1 for x, z in zip(typed, ans) if x == z), length=len(ans))
        return dict(correct=correct, y=1.0 if correct else 0.0, timed_out=False, detail=detail)
    if task == "alt_uses":
        r = score_alt_uses(item, response or "")
        return dict(correct=r.pop("correct"), y=r.pop("y"), timed_out=False, detail=r)
    if task == "word_link":
        guess = re.sub(r"[^a-zà-ÿ]", "", str(response).lower())
        correct = guess in item["answer"]
        return dict(correct=correct, y=1.0 if correct else 0.0, timed_out=False, detail=detail)
    correct = str(response) == str(item["answer"])
    y = 1.0 if correct else 0.0
    if correct and item.get("speeded"):
        y *= _speed_credit(rt_ms, item["deadline_ms"])
    return dict(correct=correct, y=y, timed_out=False, detail=detail)


def client_view(item):
    """Strip the answer before sending an item to the browser."""
    return {k: v for k, v in item.items() if k not in ("answer", "ctx_update")}
