"""Latency sources for the Apparate controller robustness study.

A *latency source* is anything callable as

    source(batch_size, profile_latency_calc_list) -> latency_calc_list

matching ``Controller._latency_source`` in ``apparate/controller.py``. The
profile passed in is Apparate's per-batch table: a list of tuples

    [(vanilla_prefix_latency_0, ramp_overhead_0),
     (vanilla_prefix_latency_1, ramp_overhead_1),
     ...,
     (vanilla_model_latency,    None)]           # last entry, overhead is None

The source returns a table of the same shape holding the latency the
controller should *perceive* this batch (e.g. under co-located memory
contention). On the board this table comes from real measurements; the
functions here synthesize it for off-board development and for the
periodicity sweep (Milestone 3).

IMPORTANT (why a scalar slowdown does nothing): Apparate's decisions depend on
latency only through ratios/differences that cancel a common factor --
``latency_improvement = (baseline - sum(exit_rate * config)) / baseline`` and
``ramp_utility = savings - overhead``. Multiplying every entry by the same s
leaves both unchanged, so a *uniform* slowdown moves no decision. Contention
must therefore be modelled *differentially*: the backbone prefix and the ramp
overhead (and/or early vs late layers) must scale by different factors. That is
also the physically realistic case, since memory-bus contention slows
memory-bound (typically early) layers more than compute-bound ones.
"""


def _scale_entry(entry, prefix_factor, overhead_factor):
    prefix, overhead = entry
    prefix = prefix * prefix_factor
    if overhead is not None:
        overhead = overhead * overhead_factor
    return (prefix, overhead)


def identity(batch_size, profile):
    """No contention. Returns the profile unchanged (baseline / sanity check)."""
    return profile


def differential(prefix_factor=1.0, overhead_factor=1.0):
    """Constant differential slowdown.

    Scales every vanilla prefix latency by ``prefix_factor`` and every ramp
    overhead by ``overhead_factor``. With the two factors equal this is a
    uniform slowdown and is a no-op on the controller's decisions; make them
    differ to shift the accuracy/latency trade-off the controller perceives.
    """
    def source(batch_size, profile):
        return [_scale_entry(e, prefix_factor, overhead_factor) for e in profile]
    return source


def depth_ramped(early_factor=1.0, late_factor=1.0):
    """Depth-dependent slowdown of the backbone prefix latencies.

    Interpolates the prefix scaling linearly with ramp depth: the first ramp's
    prefix is scaled by ``early_factor`` and the last by ``late_factor``.
    Models memory-bound early layers being slowed more than compute-bound late
    layers. Ramp overheads are left unscaled here (compute-bound heads); use
    ``differential`` on top if you also want to scale them.
    """
    def source(batch_size, profile):
        n = len(profile)
        if n <= 1:
            return list(profile)
        out = []
        for i, entry in enumerate(profile):
            frac = i / (n - 1)
            factor = early_factor + (late_factor - early_factor) * frac
            out.append(_scale_entry(entry, factor, 1.0))
        return out
    return source


class Periodic:
    """Turns any base slowdown on and off periodically over serving batches.

    The controller has no clock and calls the source once per batch, so period
    is counted in batches. For ``period`` batches per cycle, contention is
    "on" (``base_source`` applied) for the first ``duty * period`` batches and
    "off" (profile unchanged) for the rest. Used for Milestone 3: sweep
    ``period`` against Apparate's fixed re-tuning cadence
    (RAMP_CHECK_INTERVAL = 30 batches) and watch for a persistent bad
    configuration or oscillation.
    """

    def __init__(self, base_source, period, duty=0.5):
        assert period >= 1 and 0.0 < duty <= 1.0
        self._base = base_source
        self._period = period
        self._on = max(1, int(round(duty * period)))
        self._i = 0

    def reset(self):
        self._i = 0

    def is_on(self):
        return (self._i % self._period) < self._on

    def __call__(self, batch_size, profile):
        on = self.is_on()
        self._i += 1
        return self._base(batch_size, profile) if on else profile


if __name__ == "__main__":
    # Pure-Python self-test (no torch, no pickles needed).
    prof = [(10.0, 1.0), (20.0, 1.0), (30.0, None)]

    assert identity(4, prof) == prof

    d = differential(prefix_factor=2.0, overhead_factor=1.0)(4, prof)
    assert d == [(20.0, 1.0), (40.0, 1.0), (60.0, None)], d
    # uniform slowdown keeps ratios: prove the last/prefix structure scales together
    u = differential(3.0, 3.0)(4, prof)
    assert u == [(30.0, 3.0), (60.0, 3.0), (90.0, None)], u

    r = depth_ramped(early_factor=3.0, late_factor=1.0)(4, prof)
    # first prefix *3, last *1, middle *2; overheads untouched
    assert r == [(30.0, 1.0), (40.0, 1.0), (30.0, None)], r

    p = Periodic(differential(2.0, 1.0), period=4, duty=0.5)
    states = []
    for _ in range(8):
        out = p(4, prof)
        states.append(out != prof)  # True when contention is on
    assert states == [True, True, False, False, True, True, False, False], states

    print("contention_sources self-test OK")
