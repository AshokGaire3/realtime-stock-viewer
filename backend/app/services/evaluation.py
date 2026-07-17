"""Aggregate scored forecasts into accuracy-by-horizon metrics.

Headline metric is price-level error (MAE / MAPE), reported per model per
horizon and always next to the baselines, because an error of "$4.10" means
nothing until you know what random-walk scored on the same origins.

Band coverage is reported alongside: a 95% band that only contains the actual
price 60% of the time is not a 95% band, and that matters for a price-level
claim regardless of whether the point estimate is any good.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import ForecastPoint, ForecastRun


@dataclass
class HorizonMetrics:
    model: str
    step: int
    n: int
    mae: float
    mape: float  # percent
    coverage: float  # percent of actuals inside the 95% band
    direction_acc: float  # percent; secondary, reported but not headline

    @property
    def mape_str(self) -> str:
        return f"{self.mape:.2f}%"


def metrics_by_horizon(
    session: Session, steps: list[int] | None = None, symbol: str | None = None
) -> list[HorizonMetrics]:
    """Per-model, per-step accuracy over all scored backtest points."""
    q = (
        select(
            ForecastRun.model,
            ForecastPoint.step,
            ForecastPoint.abs_error,
            ForecastPoint.pct_error,
            ForecastPoint.in_band,
            ForecastPoint.direction_hit,
        )
        .join(ForecastRun, ForecastPoint.run_id == ForecastRun.id)
        .where(ForecastPoint.actual != None)  # noqa: E711
        .where(ForecastRun.is_backtest == True)  # noqa: E712
    )
    if symbol:
        q = q.where(ForecastRun.symbol == symbol.upper())
    if steps:
        q = q.where(ForecastPoint.step.in_(steps))

    buckets: dict[tuple[str, int], list[tuple]] = {}
    for model, step, abs_err, pct_err, in_band, dir_hit in session.exec(q).all():
        buckets.setdefault((model, step), []).append((abs_err, pct_err, in_band, dir_hit))

    out: list[HorizonMetrics] = []
    for (model, step), rows in sorted(buckets.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        n = len(rows)
        out.append(
            HorizonMetrics(
                model=model,
                step=step,
                n=n,
                mae=sum(r[0] for r in rows) / n,
                mape=100 * sum(r[1] for r in rows) / n,
                coverage=100 * sum(1 for r in rows if r[2]) / n,
                direction_acc=100 * sum(1 for r in rows if r[3]) / n,
            )
        )
    return out


def format_report(metrics: list[HorizonMetrics], baseline: str = "random-walk") -> str:
    """Render metrics as a text table, with each model's MAE vs the baseline."""
    by_step: dict[int, dict[str, HorizonMetrics]] = {}
    for m in metrics:
        by_step.setdefault(m.step, {})[m.model] = m

    lines = [
        f"{'horizon':>8} {'model':<14} {'n':>6} {'MAE':>9} {'MAPE':>8} "
        f"{'vs base':>9} {'coverage':>9} {'dir acc':>8}",
        "-" * 78,
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
            lines.append(
                f"{f'{step}d':>8} {m.model:<14} {m.n:>6} {m.mae:>9.3f} "
                f"{m.mape:>7.2f}% {vs:>9} {m.coverage:>8.1f}% {m.direction_acc:>7.1f}%"
            )
        lines.append("")
    lines.append(f"'vs base' = MAE relative to {baseline}; negative is better, positive is worse.")
    return "\n".join(lines)
