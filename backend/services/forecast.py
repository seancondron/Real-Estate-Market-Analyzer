import numpy as np
from sklearn.ensemble import GradientBoostingRegressor

N_BACK = 4  # lag quarters used as features

_RATE_DELTA = {'current': 0.0, 'falling': -0.12, 'rising': 0.10}


def _ffill(rates):
    filled, last = [], 5.5
    for r in rates:
        if r is not None:
            last = float(r)
        filled.append(last)
    return filled


def _make_features(prices, rates):
    X, y = [], []
    for i in range(N_BACK, len(prices)):
        lags    = [prices[i - j] for j in range(1, N_BACK + 1)]
        t       = float(i)
        sin_q   = np.sin(2 * np.pi * (i % 4) / 4)
        cos_q   = np.cos(2 * np.pi * (i % 4) / 4)
        row     = lags + [t, sin_q, cos_q, rates[i]]
        X.append(row)
        y.append(prices[i])
    return np.array(X, dtype=float), np.array(y, dtype=float)


def _gb(loss='squared_error'):
    return GradientBoostingRegressor(
        n_estimators=120, learning_rate=0.06, max_depth=2,
        min_samples_leaf=2, subsample=0.85, random_state=42,
        loss=loss,
    )


def ml_forecast(prices, rates, n_quarters=8, rate_scenario='current'):
    """
    Train a GradientBoosting model on quarterly prices and project forward.

    Returns (forecast, ci_lower, ci_upper) as lists of ints.
    """
    prices = [float(p) for p in prices]
    rates  = _ffill(rates)

    if len(prices) < N_BACK + 3:
        last = prices[-1]
        fc   = [round(last * (1.005 ** (i + 1))) for i in range(n_quarters)]
        ci   = [round(last * 0.022 * (i + 1))    for i in range(n_quarters)]
        return fc, [f - c for f, c in zip(fc, ci)], [f + c for f, c in zip(fc, ci)]

    X, y = _make_features(prices, rates)

    med = _gb('squared_error')
    lo  = _gb('quantile')
    lo.set_params(alpha=0.15)
    hi  = _gb('quantile')
    hi.set_params(alpha=0.85)

    med.fit(X, y)
    lo.fit(X, y)
    hi.fit(X, y)

    # Residual std on training data — used to widen CI over the horizon
    base_err = float(np.std(y - med.predict(X)))

    rate_delta   = _RATE_DELTA.get(rate_scenario, 0.0)
    cur_prices   = list(prices)
    cur_rate     = rates[-1]
    forecast, ci_lo, ci_hi = [], [], []

    for i in range(n_quarters):
        t     = float(len(prices) + i)
        sin_q = np.sin(2 * np.pi * (int(t) % 4) / 4)
        cos_q = np.cos(2 * np.pi * (int(t) % 4) / 4)
        cur_rate = float(np.clip(cur_rate + rate_delta, 2.5, 12.0))
        lags  = [cur_prices[-(j)] for j in range(1, N_BACK + 1)]
        row   = np.array(lags + [t, sin_q, cos_q, cur_rate], dtype=float).reshape(1, -1)

        p_med = float(med.predict(row)[0])
        p_lo  = float(lo.predict(row)[0])
        p_hi  = float(hi.predict(row)[0])

        # Widen bounds proportionally to how far into the future we are
        half   = max((p_hi - p_lo) / 2, base_err) * (1.0 + i * 0.20)
        p_lo   = p_med - half
        p_hi   = p_med + half

        forecast.append(round(p_med))
        ci_lo.append(round(p_lo))
        ci_hi.append(round(p_hi))
        cur_prices.append(p_med)

    return forecast, ci_lo, ci_hi
