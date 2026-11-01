"""Bayesian ability estimation on a discrete grid.

Each dimension holds a posterior over a latent ability theta. Items follow a 3PL
item response model:

    P(correct | theta) = c + (1 - c) * logistic(a * (theta - b))

Evidence is a fractional outcome y in [0, 1] with a reliability weight w in [0, 1],
so a trial contributes  w * [y log p + (1 - y) log(1 - p)]  to the log-posterior.
Between sessions the posterior is diffused, so uncertainty grows while no new
evidence arrives. That makes the profile dynamic instead of a fixed test result.
"""

import numpy as np

GRID = np.linspace(-4.0, 4.0, 161)
PRIOR_SD = 1.5
LEVELS = 10
DIFFICULTY_LADDER = np.array([-2.7 + 0.6 * i for i in range(LEVELS)])
REFERENCE_A = 1.2

# Daily diffusion of theta. After 30 idle days it adds a variance of 0.36, or an SD of 0.6.
DRIFT_VAR_PER_DAY = 0.012
# Minimum diffusion per new session, so old evidence never fully pins the estimate and
# the twin can follow someone who is improving. Tuned on the tracking study in run_eval.py.
DRIFT_VAR_PER_SESSION = 0.06


def level_to_b(level):
    return float(DIFFICULTY_LADDER[int(level) - 1])


def _logistic(x):
    return 1.0 / (1.0 + np.exp(-x))


def theta_to_pct(theta):
    """Expected score on a balanced reference test spanning the difficulty ladder."""
    theta = np.asarray(theta, dtype=float)
    return 100.0 * _logistic(REFERENCE_A * (theta[..., None] - DIFFICULTY_LADDER)).mean(axis=-1)


PCT_GRID = theta_to_pct(GRID)


def pct_to_theta(pct):
    return float(np.interp(pct, PCT_GRID, GRID))


def item_prob(theta, a, b, c):
    return c + (1.0 - c) * _logistic(a * (np.asarray(theta, dtype=float) - b))


def item_information(theta, a, b, c):
    """3PL Fisher information of an item at theta."""
    p = np.clip(item_prob(theta, a, b, c), 1e-6, 1 - 1e-6)
    return a * a * ((1.0 - p) / p) * ((p - c) / (1.0 - c)) ** 2


class Posterior:
    def __init__(self, log_density=None):
        if log_density is None:
            log_density = -0.5 * (GRID / PRIOR_SD) ** 2
        self.log = np.asarray(log_density, dtype=float)
        self._normalise()

    def _normalise(self):
        self.log = self.log - self.log.max()

    @property
    def density(self):
        d = np.exp(self.log)
        return d / d.sum()

    def update(self, a, b, c, y, w=1.0):
        """Apply one trial. y is a fractional outcome, w an evidence weight."""
        y = float(np.clip(y, 0.0, 1.0))
        w = float(np.clip(w, 0.0, 1.0))
        p = np.clip(item_prob(GRID, a, b, c), 1e-6, 1 - 1e-6)
        self.log = self.log + w * (y * np.log(p) + (1.0 - y) * np.log(1.0 - p))
        self._normalise()
        return self

    def drift(self, variance):
        """Diffuse the posterior: uncertainty grows when evidence goes stale."""
        if variance <= 0:
            return self
        step = GRID[1] - GRID[0]
        half = int(np.ceil(4 * np.sqrt(variance) / step))
        if half < 1:
            return self
        offsets = np.arange(-half, half + 1) * step
        kernel = np.exp(-0.5 * offsets ** 2 / variance)
        kernel /= kernel.sum()
        # Edge-normalised convolution, so mass near the grid ends is not lost.
        mass = np.convolve(np.ones_like(GRID), kernel, mode="same")
        smoothed = np.convolve(self.density, kernel, mode="same") / mass
        self.log = np.log(np.maximum(smoothed, 1e-300))
        self._normalise()
        return self

    def mean(self):
        return float((self.density * GRID).sum())

    def sd(self):
        d = self.density
        m = (d * GRID).sum()
        return float(np.sqrt((d * (GRID - m) ** 2).sum()))

    def quantile(self, q):
        cdf = np.cumsum(self.density)
        return float(np.interp(q, cdf, GRID))

    def pct(self):
        return float((self.density * PCT_GRID).sum())

    def pct_interval(self, mass=0.90):
        tail = (1.0 - mass) / 2.0
        low, high = self.quantile(tail), self.quantile(1.0 - tail)
        return float(theta_to_pct(low)), float(theta_to_pct(high))

    def prob_at_least(self, pct):
        """Probability that the true percentage is at or above pct."""
        return float(self.density[PCT_GRID >= pct].sum())

    def predicted_success(self, a, b, c):
        return float((self.density * item_prob(GRID, a, b, c)).sum())

    def summary(self):
        low, high = self.pct_interval()
        return {
            "theta": round(self.mean(), 4),
            "theta_sd": round(self.sd(), 4),
            "pct": round(self.pct(), 1),
            "low": round(low, 1),
            "high": round(high, 1),
        }

    def to_list(self):
        return [round(float(x), 4) for x in self.log]

    @classmethod
    def from_list(cls, values):
        return cls(np.array(values, dtype=float))


def choose_level_for_information(posterior, a, c, rng=None, avoid=None):
    """Assessment mode: the level that is most informative at the current estimate."""
    theta = posterior.mean()
    info = item_information(theta, a, DIFFICULTY_LADDER, c)
    order = np.argsort(-info)
    pick = order[0]
    # A little randomness between the top two levels keeps sequences from being predictable.
    if rng is not None and len(order) > 1 and rng.random() < 0.3:
        pick = order[1]
    return int(pick) + 1


def choose_level_for_success(posterior, a, c, target=0.80):
    """Training mode: the level whose predicted success rate is closest to target.

    The default sits just under the 85% optimum reported by Wilson et al. (2019).
    """
    gaps = [abs(posterior.predicted_success(a, b, c) - target) for b in DIFFICULTY_LADDER]
    return int(np.argmin(gaps)) + 1
