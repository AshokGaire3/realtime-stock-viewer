"""Aggregate scored forecasts into accuracy-by-horizon metrics.

Headline metric is price-level error (MAE / MAPE), reported per model per
horizon and always next to the baselines, because an error of "$4.10" means
nothing until you know what random-walk scored on the same origins.

Band coverage is reported alongside: a 95% band that only contains the actual
price 60% of the time is not a 95% band, and that matters for a price-level
claim regardless of whether the point estimate is any good.

**On sample size.** Raw point count overstates what's known: origins overlap
(a stride shorter than the horizon reuses nearby bars) and symbols move
together at shared timestamps, so points are not independent draws. The unit
of real information is closer to one (symbol, calendar day) cluster. Anything
that reports a sample size reports both: `n` (raw points) and `n_clusters`
(distinct symbol-days) — and the bootstrap CIs are resampled over clusters,
not points, so cluster correlation doesn't masquerade as precision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date

import numpy as np
from sqlmodel import Session, select

from app.models import ForecastPoint, ForecastRun
from app.schemas import ModelAccuracy
from app.services.forecasters import MODELS

_BOOTSTRAP_RESAMPLES = 2000
_BOOTSTRAP_SEED = 0


@dataclass
class HorizonMetrics:
    model: str
    step: int
    n: int  # raw scored points
    n_clusters: int  # distinct (symbol, as_of day) origins — the effective sample size
    mae: float
    mape: float  # percent
    mae_ci: tuple[float, float]  # 95% bootstrap CI on MAE, resampled over clusters
    coverage: float  # percent of actuals inside the 95% band
    direction_acc: float  # percent; secondary, reported but not headline

    @property
    def mape_str(self) -> str:
        return f"{self.mape:.2f}%"


def _cluster_bootstrap_ci(
    clustered: dict[tuple[str, Date], list[float]],
    resamples: int = _BOOTSTRAP_RESAMPLES,
    seed: int = _BOOTSTRAP_SEED,
) -> tuple[float, float]:
    """95% CI on the mean, resampling whole (symbol, day) clusters with replacement.

    Resampling points directly would treat correlated same-day, same-symbol
    errors as independent evidence and understate the interval. Resampling
    clusters instead means the interval reflects the true effective sample
    size, not the inflated raw count.
    """
    keys = list(clustered.keys())
    if len(keys) < 2:
        nan = float("nan")
        return nan, nan
    rng = np.random.default_rng(seed)
    idx = np.arange(len(keys))
    means = np.empty(resamples)
    for r in range(resamples):
        picked = rng.choice(idx, size=len(idx), replace=True)
        vals = [v for i in picked for v in clustered[keys[i]]]
        means[r] = float(np.mean(vals))
    means.sort()
    lo = float(means[int(0.025 * resamples)])
    hi = float(means[min(int(0.975 * resamples), resamples - 1)])
    return lo, hi


def metrics_by_horizon(
    session: Session,
    steps: list[int] | None = None,
    symbol: str | None = None,
    interval: str = "1d",
    is_backtest: bool | None = True,
) -> list[HorizonMetrics]:
    """Per-model, per-step accuracy over all scored points.

    `is_backtest=True` (default) scores the walk-forward backtest; `False`
    scores live /api/predict runs; `None` pools both.
    """
    q = (
        select(
            ForecastRun.model,
            ForecastRun.symbol,
            ForecastRun.as_of_ts,
            ForecastPoint.step,
            ForecastPoint.abs_error,
            ForecastPoint.pct_error,
            ForecastPoint.in_band,
            ForecastPoint.direction_hit,
        )
        .join(ForecastRun, ForecastPoint.run_id == ForecastRun.id)
        .where(ForecastPoint.actual != None)  # noqa: E711
        .where(ForecastRun.interval == interval)
    )
    if is_backtest is not None:
        q = q.where(ForecastRun.is_backtest == is_backtest)
    if symbol:
        q = q.where(ForecastRun.symbol == symbol.upper())
    if steps:
        q = q.where(ForecastPoint.step.in_(steps))

    buckets: dict[tuple[str, int], list[tuple]] = {}
    for model, sym, as_of_ts, step, abs_err, pct_err, in_band, dir_hit in session.exec(q).all():
        cluster = (sym, as_of_ts.date())
        buckets.setdefault((model, step), []).append(
            (abs_err, pct_err, in_band, dir_hit, cluster)
        )

    out: list[HorizonMetrics] = []
    for (model, step), rows in sorted(buckets.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        n = len(rows)
        clustered_mae: dict[tuple[str, Date], list[float]] = {}
        for abs_err, *_rest, cluster in rows:
            clustered_mae.setdefault(cluster, []).append(abs_err)
        out.append(
            HorizonMetrics(
                model=model,
                step=step,
                n=n,
                n_clusters=len(clustered_mae),
                mae=sum(r[0] for r in rows) / n,
                mape=100 * sum(r[1] for r in rows) / n,
                mae_ci=_cluster_bootstrap_ci(clustered_mae),
                coverage=100 * sum(1 for r in rows if r[2]) / n,
                direction_acc=100 * sum(1 for r in rows if r[3]) / n,
            )
        )
    return out


def paired_loss_diff(
    session: Session,
    model: str,
    step: int,
    baseline: str = "random-walk",
    interval: str = "1d",
    symbol: str | None = None,
    is_backtest: bool | None = True,
) -> dict | None:
    """Is `model` actually better than `baseline`, on the identical origins?

    Compares pooled MAE across two different sets of runs; two symbols' worth
    of noise can move that comparison as much as a real skill difference.
    Pairing per origin (same symbol, same as_of bar) cancels out everything
    origin-specific — the volatility of that particular week, that particular
    stock — and leaves only the difference the model itself made. Returns None
    if there are fewer than 2 (symbol, day) clusters to resample over.
    """
    q = (
        select(
            ForecastRun.model,
            ForecastRun.symbol,
            ForecastRun.as_of_ts,
            ForecastPoint.abs_error,
        )
        .join(ForecastRun, ForecastPoint.run_id == ForecastRun.id)
        .where(ForecastRun.model.in_([model, baseline]))
        .where(ForecastRun.interval == interval)
        .where(ForecastPoint.step == step)
        .where(ForecastPoint.actual != None)  # noqa: E711
    )
    if is_backtest is not None:
        q = q.where(ForecastRun.is_backtest == is_backtest)
    if symbol:
        q = q.where(ForecastRun.symbol == symbol.upper())

    losses: dict[tuple[str, object], dict[str, float]] = {}
    for m, sym, as_of_ts, abs_err in session.exec(q).all():
        origin = (sym, as_of_ts)
        losses.setdefault(origin, {})[m] = abs_err

    diffs_by_day: dict[tuple[str, Date], list[float]] = {}
    for (sym, as_of_ts), by_model in losses.items():
        if model not in by_model or baseline not in by_model:
            continue  # only origins where both models were actually run
        diffs_by_day.setdefault((sym, as_of_ts.date()), []).append(
            by_model[model] - by_model[baseline]
        )

    n_pairs = sum(len(v) for v in diffs_by_day.values())
    if len(diffs_by_day) < 2:
        return None

    lo, hi = _cluster_bootstrap_ci(diffs_by_day)
    mean_diff = float(np.mean([d for v in diffs_by_day.values() for d in v]))
    return {
        "model": model,
        "baseline": baseline,
        "step": step,
        "n_pairs": n_pairs,
        "n_clusters": len(diffs_by_day),
        "mean_diff": mean_diff,  # negative means `model` beats `baseline` on MAE
        "ci": (lo, hi),
        "significant": hi < 0 or lo > 0,  # CI excludes zero
    }


def accuracy_for(
    session: Session,
    model: str,
    horizon: int,
    baseline: str = "random-walk",
    symbol: str | None = None,
    interval: str = "1d",
    is_backtest: bool | None = True,
) -> ModelAccuracy | None:
    """Measured accuracy for one model at one horizon, for the live endpoint.

    Returns None when no backtest has been run — the endpoint then reports no
    accuracy at all, which is the honest answer. Inventing a number here is the
    exact failure we removed.

    `is_backtest=None` pools backtest and live-scored evidence — pass the same
    value used by `select_model` so the reported accuracy always describes the
    evidence that actually picked the model, not a different slice of it.
    """
    metrics = metrics_by_horizon(
        session, steps=[horizon], symbol=symbol, interval=interval, is_backtest=is_backtest
    )
    by_model = {m.model: m for m in metrics}
    me, base = by_model.get(model), by_model.get(baseline)
    if me is None or base is None:
        return None
    return ModelAccuracy(
        horizon_days=horizon,
        mape=round(me.mape, 2),
        baseline_mape=round(base.mape, 2),
        # Compared on MAPE, the same metric exposed here — comparing on MAE
        # while reporting MAPE let the two fields disagree on which model won.
        beats_baseline=me.mape < base.mape,
        n_forecasts=me.n,
    )


def select_model(
    session: Session,
    horizon: int,
    candidates: list[str] | None = None,
    baseline: str = "random-walk",
    interval: str = "1d",
    is_backtest: bool | None = None,
) -> str:
    """Which model should serve this horizon, right now.

    This is the whole self-improving mechanism: it returns a candidate only if
    `paired_loss_diff` finds it *significantly* better than `baseline` (the
    bootstrap CI excludes zero) on the identical origins — never just "lowest
    MAPE today", which one lucky symbol could produce. Pooled across all
    symbols (`symbol=None` in the underlying queries) rather than per-symbol,
    because per-symbol cluster counts are too small for the significance test
    to ever fire; pooled sample sizes are where it has real power.

    `is_backtest=None` (the default) pools the walk-forward backtest with
    every live forecast `scripts/collect.py` has since labeled against
    reality — both cluster by `(symbol, as_of day)` the same way, so pooling
    adds evidence and recency without weakening the statistics. This is what
    makes the answer actually change as live predictions get scored correct
    or incorrect, with no code change and no redeploy — the improvement loop.
    """
    if candidates is None:
        candidates = [m for m in MODELS if m != baseline]

    winners = []
    for model in candidates:
        diff = paired_loss_diff(
            session, model, horizon, baseline=baseline, interval=interval, is_backtest=is_backtest
        )
        if diff and diff["significant"] and diff["mean_diff"] < 0:
            winners.append(model)

    if not winners:
        return baseline

    metrics = {
        m.model: m
        for m in metrics_by_horizon(session, steps=[horizon], interval=interval, is_backtest=is_backtest)
    }
    return min(winners, key=lambda m: metrics[m].mae)


def todays_scored_points(
    session: Session, symbol: str, interval: str = "60m", model: str | None = None
) -> list[dict]:
    """The label ledger for the intraday showcase: every live (`is_backtest`
    False) forecast point logged for `symbol` on the most recent trading day
    present in the corpus, oldest first. Not filtered by calendar "today" so
    it still shows something sensible when queried outside market hours.
    """
    q = (
        select(ForecastRun, ForecastPoint)
        .join(ForecastPoint, ForecastPoint.run_id == ForecastRun.id)
        .where(ForecastRun.symbol == symbol.upper())
        .where(ForecastRun.interval == interval)
        .where(ForecastRun.is_backtest == False)  # noqa: E712
    )
    if model:
        q = q.where(ForecastRun.model == model)
    rows = session.exec(q).all()
    if not rows:
        return []

    latest_day = max(run.as_of_ts.date() for run, _ in rows)
    day_rows = sorted(
        (rp for rp in rows if rp[0].as_of_ts.date() == latest_day),
        key=lambda rp: (rp[0].as_of_ts, rp[1].step),
    )
    return [
        {
            "as_of": run.as_of_ts.isoformat(timespec="minutes"),
            "target": point.target_ts.isoformat(timespec="minutes") if point.target_ts else None,
            "model": run.model,
            "predicted": point.predicted,
            "actual": point.actual,
            "abs_error": point.abs_error,
            "direction_hit": point.direction_hit,
        }
        for run, point in day_rows
    ]


def format_report(metrics: list[HorizonMetrics], baseline: str = "random-walk") -> str:
    """Render metrics as a text table, with each model's MAE vs the baseline."""
    by_step: dict[int, dict[str, HorizonMetrics]] = {}
    for m in metrics:
        by_step.setdefault(m.step, {})[m.model] = m

    lines = [
        f"{'step':>6} {'model':<14} {'n':>7} {'n_days':>7} {'MAE':>9} {'MAE 95% CI':>18} "
        f"{'MAPE':>8} {'vs base':>9} {'coverage':>9} {'dir acc':>8}",
        "-" * 108,
    ]
    for step in sorted(by_step):
        base = by_step[step].get(baseline)
        for model in sorted(by_step[step]):
            m = by_step[step][model]
            if base and base.mae and model != baseline:
                delta = 100 * (m.mae - base.mae) / base.mae
                vs = f"{delta:+.1f}%"
            else:
                vs = "—" if model == baseline else "n/a"
            ci = f"[{m.mae_ci[0]:.3f}, {m.mae_ci[1]:.3f}]"
            lines.append(
                f"{step:>6} {m.model:<14} {m.n:>7} {m.n_clusters:>7} {m.mae:>9.3f} {ci:>18} "
                f"{m.mape:>7.2f}% {vs:>9} {m.coverage:>8.1f}% {m.direction_acc:>7.1f}%"
            )
        lines.append("")
    lines.append(
        f"'vs base' = MAE relative to {baseline}; negative is better, positive is worse.\n"
        "'n_days' = distinct (symbol, day) clusters — the effective sample size behind the "
        "CI; 'n' is raw scored points and overstates it when origins overlap or symbols move "
        "together."
    )
    return "\n".join(lines)
