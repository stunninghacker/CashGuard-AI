"""
Self-exciting (Hawkes) intensity model over COMPLAINT timestamps.

λ(t) = μ + Σ_{tᵢ < t} α · exp(−β·(t − tᵢ))

* μ        : baseline complaint rate per day
* α, β     : excitation strength / decay — fitted per LOCATION (city) by
             grid-search maximum likelihood on the TRAINING period only.
* Stability: α < β enforced (otherwise the process is explosive); α/β < 1.
* PREDICTION-TIME SAFETY (by construction + asserted):
     only events with tᵢ < t enter the sum. Events at or after t (including
     future test-period complaints) are excluded by a strict-mask, and the
     self-test below asserts it.

The fitted parameters are saved in the model artifact; inference reuses them —
never refits on data it must predict.
"""
from __future__ import annotations

import numpy as np

__all__ = ["fit_location_params", "intensity_at", "self_test"]


def _log_likelihood(times: np.ndarray, horizon: float, mu: float, alpha: float, beta: float) -> float:
    """Exact O(N) log-likelihood via the exponential-kernel recurrence.

    LL = Σᵢ ln(μ + Sᵢ) − [μ·T + (α/β)·Σⱼ(1 − exp(−β·(T − tⱼ)))]
    where Sᵢ = α·exp(−β·Δtᵢ)·(1 + Sᵢ₋₁/α) follows the renewal trick.
    """
    if alpha >= beta:
        return -np.inf  # stability constraint: α < β
    dt = np.diff(times) if len(times) > 1 else np.array([0.0])
    s = 0.0
    ll = 0.0
    for i, t in enumerate(times):
        if i > 0:
            s = alpha * np.exp(-beta * dt[i - 1]) + s * np.exp(-beta * dt[i - 1])
            # equivalent: s = (s + alpha) * exp(-beta * dt[i-1])
        else:
            s = 0.0
        ll += np.log(max(mu + s, 1e-12))
    integral = mu * horizon + (alpha / beta) * (len(times) - (np.exp(-beta * (horizon - times))).sum())
    return ll - integral


def fit_location_params(
    event_times: np.ndarray,
    horizon: float,
    betas: np.ndarray | None = None,
    alpha_fracs: np.ndarray | None = None,
) -> tuple[float, float, float]:
    """
    Fit (mu, alpha, beta) for one location via grid-search MLE.

    event_times : complaint timestamps as float DAYS relative to a fixed epoch,
                  strictly within the TRAINING period (caller guarantees).
    horizon     : end of the training window (days).
    Stability enforced: alpha = frac * beta with frac in (0, 1) → α < β.
    """
    times = np.sort(np.asarray(event_times, dtype=float))
    if len(times) < 2:
        return float(len(times) / max(horizon, 1.0)), 0.0, 0.1
    mu = max(len(times) / horizon, 1e-6)
    betas = betas if betas is not None else np.array([0.05, 0.1, 0.2, 0.4, 0.8, 1.5])
    alpha_fracs = alpha_fracs if alpha_fracs is not None else np.array([0.1, 0.25, 0.5, 0.75, 0.95])
    best = (mu, 0.0, betas[0])
    best_ll = -np.inf
    for beta in betas:
        for frac in alpha_fracs:
            alpha = frac * beta  # guarantees alpha < beta
            ll = _log_likelihood(times, horizon, mu, alpha, beta)
            if ll > best_ll:
                best_ll, best = ll, (float(mu), float(alpha), float(beta))
    return best


def intensity_at(
    days: np.ndarray,
    event_times: np.ndarray,
    mu: float,
    alpha: float,
    beta: float,
) -> np.ndarray:
    """
    λ(d) for each d in `days`.

    STRICT-mask: only events with tᵢ < d contribute — future events at/after d
    are excluded by construction (prediction-time safety).
    """
    days = np.asarray(days, dtype=float)
    events = np.asarray(event_times, dtype=float)
    if len(events) == 0:
        return np.full_like(days, float(mu))
    diff = days[:, None] - events[None, :]          # (n_days, n_events)
    mask = diff > 0.0                                # tᵢ < d ONLY (strict)
    contrib = alpha * np.exp(-beta * np.where(mask, diff, 0.0))
    return float(mu) + (contrib * mask).sum(axis=1)


def self_test() -> None:
    """Prediction-time-safety unit check: future events must NOT enter λ."""
    rng = np.random.default_rng(7)
    events = np.sort(rng.uniform(0.0, 30.0, 40))
    mu, alpha, beta = fit_location_params(events, horizon=30.0)
    days = np.array([15.0, 30.0, 45.0])
    lam = intensity_at(days, events, mu, alpha, beta)
    # fabricate events strictly AFTER the last queried day (45) — λ must not change
    future = np.array([46.0, 50.0, 60.0, 90.0])
    lam_with_future = intensity_at(days, np.concatenate([events, future]), mu, alpha, beta)
    assert np.allclose(lam, lam_with_future, atol=1e-9), (
        "future events leaked into the intensity sum — prediction-time safety broken"
    )
    # a PAST event between days MUST increase later λ (self-excitation, not leakage)
    lam_with_past = intensity_at(days, np.concatenate([events, [35.0]]), mu, alpha, beta)
    assert lam_with_past[2] > lam[2], "past events must excite later intensity"
    assert alpha < beta, "stability constraint α < β violated"
    assert np.isfinite(lam).all() and (lam >= 0).all()
    print(f"[hawkes] self-test OK (mu={mu:.3f}, alpha={alpha:.3f}, beta={beta:.3f}) — future-free by construction")