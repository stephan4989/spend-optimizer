"""
Mock Celery task: fit_model (demo / macOS fallback)

Simulates the full pipeline with realistic timing and synthetic results.
Activated by setting the environment variable MOCK_MMM=1.
The real fit_model.py is unchanged — this file shadows it at dispatch time.
"""
from __future__ import annotations

import io
import logging
import math
import random
import time

import pandas as pd

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_PROGRESS_STEPS = [
    (5,  "fitting",    0.5),
    (15, "fitting",    1.0),
    (30, "fitting",    1.5),
    (45, "fitting",    1.5),
    (60, "fitting",    1.0),
    (75, "fitting",    1.0),
    (82, "fitting",    0.5),
    (88, "optimizing", 1.0),
    (95, "optimizing", 0.5),
    (100, "completed", 0),
]


@celery_app.task(bind=True, name="tasks.fit_model", max_retries=0)
def fit_model(self, payload: dict) -> None:
    run_id: str = payload["run_id"]
    upload_id: str = payload["upload_id"]
    channel_names: list[str] = payload["channel_names"]
    total_budget: float = payload["total_budget"]
    channel_constraints_raw: dict = payload.get("channel_constraints", {})

    import redis as sync_redis
    from app.config import get_settings
    from app.models.run import RunStatus
    from app.models.results import ModelDiagnostics, ModelFitData, ContributionData, RunResults, ResponseCurveData

    settings = get_settings()
    r = sync_redis.from_url(settings.REDIS_URL, decode_responses=False)

    # Reuse the sync helpers from the real task
    from app.tasks.fit_model import _SyncRunRepo, _SyncUploadRepo, _get_run_label
    run_repo = _SyncRunRepo(r, settings.SESSION_TTL_SECONDS)
    upload_repo = _SyncUploadRepo(r)

    def set_progress(pct: int, status_str: str) -> None:
        status = RunStatus(status_str) if status_str != "completed" else RunStatus.completed
        run_repo.update_status(run_id, status, progress_pct=pct)

    try:
        # Load CSV so we can derive realistic spend figures
        raw_csv = upload_repo.get_raw_csv(upload_id)
        df = pd.read_csv(io.BytesIO(raw_csv)) if raw_csv else None

        # Simulate progress steps with short sleeps
        for pct, status_str, sleep_s in _PROGRESS_STEPS[:-1]:
            set_progress(pct, status_str)
            time.sleep(sleep_s)

        # ── Build synthetic results ────────────────────────────────────────
        rng = random.Random(42)
        run_label = _get_run_label(r, run_id)

        # Prior allocation: proportional to historical mean spend
        if df is not None and all(ch in df.columns for ch in channel_names):
            mean_spend = {ch: df[ch].mean() for ch in channel_names}
        else:
            mean_spend = {ch: rng.uniform(10000, 60000) for ch in channel_names}

        total_mean = sum(mean_spend.values())
        prior_allocation = {
            ch: round(total_budget * mean_spend[ch] / total_mean, 2)
            for ch in channel_names
        }

        # Synthetic ROI per channel (random but plausible)
        roi = {ch: rng.uniform(0.8, 4.5) for ch in channel_names}

        # Response curves: Hill saturation shape per channel
        response_curves: dict[str, ResponseCurveData] = {}
        for ch in channel_names:
            max_spend = prior_allocation[ch] * 2.5
            n_points = 40
            spend_points = [round(max_spend * i / (n_points - 1)) for i in range(n_points)]
            ec = prior_allocation[ch] * rng.uniform(0.6, 1.4)   # half-saturation point
            slope = rng.uniform(1.2, 2.8)
            scale = roi[ch] * ec * rng.uniform(80, 120)          # rough total acq at saturation

            def hill(x: float, ec: float = ec, s: float = slope) -> float:
                if x <= 0:
                    return 0.0
                return (x ** s) / (ec ** s + x ** s)

            acqs = [scale * hill(s) for s in spend_points]
            noise = [rng.uniform(0.92, 1.08) for _ in spend_points]
            ci_lower = [a * n * 0.85 for a, n in zip(acqs, noise)]
            ci_upper = [a * n * 1.15 for a, n in zip(acqs, noise)]

            response_curves[ch] = ResponseCurveData(
                spend_points=[float(s) for s in spend_points],
                acquisitions=[round(a, 1) for a in acqs],
                ci_lower=[round(c, 1) for c in ci_lower],
                ci_upper=[round(c, 1) for c in ci_upper],
            )

        # Optimised allocation: shift budget towards highest-ROI channels
        sorted_channels = sorted(channel_names, key=lambda ch: roi[ch], reverse=True)
        # Top half gets 65% of budget, bottom half gets 35%
        n = len(sorted_channels)
        top = sorted_channels[: max(1, n // 2)]
        bottom = sorted_channels[max(1, n // 2):]

        def distribute(channels, share):
            weights = {ch: roi[ch] for ch in channels}
            total_w = sum(weights.values())
            return {ch: round(total_budget * share * weights[ch] / total_w, 2) for ch in channels}

        optimized_allocation = {}
        optimized_allocation.update(distribute(top, 0.65))
        if bottom:
            optimized_allocation.update(distribute(bottom, 0.35))

        # Respect min/max constraints
        for ch in channel_names:
            c = channel_constraints_raw.get(ch, {})
            lo = total_budget * c.get("min_fraction", 0)
            hi = total_budget * c.get("max_fraction", 1)
            optimized_allocation[ch] = round(max(lo, min(hi, optimized_allocation.get(ch, 0))), 2)

        # Acquisitions
        def total_acq(alloc: dict) -> float:
            total = 0.0
            for ch in channel_names:
                curve = response_curves[ch]
                pts = curve.spend_points
                acqs = curve.acquisitions
                s = alloc.get(ch, 0)
                for j in range(len(pts) - 1):
                    if pts[j] <= s <= pts[j + 1]:
                        t = (s - pts[j]) / (pts[j + 1] - pts[j] + 1e-9)
                        total += acqs[j] + t * (acqs[j + 1] - acqs[j])
                        break
                else:
                    total += acqs[-1] if s >= pts[-1] else 0
            return total

        prior_acq = total_acq(prior_allocation)
        opt_acq = total_acq(optimized_allocation)
        lift_pct = round((opt_acq - prior_acq) / max(prior_acq, 1) * 100, 2)

        # ── Synthetic time-series analytics ───────────────────────────────
        n_rows = len(df) if df is not None else 52
        dates: list[str] = []
        if df is not None and "date" in df.columns:
            dates = df["date"].astype(str).tolist()
        else:
            import datetime
            base = datetime.date(2023, 1, 2)
            dates = [(base + datetime.timedelta(weeks=w)).isoformat() for w in range(n_rows)]

        # Actual acquisitions: sinusoidal seasonal pattern
        actual_acq = [
            round(prior_acq * (0.85 + 0.3 * math.sin(2 * math.pi * t / 52) + rng.uniform(-0.08, 0.08)), 1)
            for t in range(n_rows)
        ]
        if df is not None and "acquisitions" in df.columns:
            actual_acq = df["acquisitions"].tolist()

        # Predicted ≈ actual ± small noise, CI wider
        predicted_mean = [round(a * rng.uniform(0.95, 1.05), 1) for a in actual_acq]
        predicted_lower = [round(p * 0.88, 1) for p in predicted_mean]
        predicted_upper = [round(p * 1.12, 1) for p in predicted_mean]

        model_fit = ModelFitData(
            dates=dates,
            actual=actual_acq,
            predicted_mean=predicted_mean,
            predicted_lower=predicted_lower,
            predicted_upper=predicted_upper,
        )

        # Channel contributions: each channel gets a noisy fraction of actual
        total_roi = sum(roi.values())
        contrib_dict: dict[str, list[float]] = {}
        for ch in channel_names:
            ch_share = roi[ch] / total_roi
            contrib_dict[ch] = [
                round(a * ch_share * rng.uniform(0.85, 1.15), 1) for a in actual_acq
            ]

        contributions = ContributionData(dates=dates, contributions=contrib_dict)

        results = RunResults(
            run_id=run_id,
            run_label=run_label,
            channels=channel_names,
            response_curves=response_curves,
            prior_allocation=prior_allocation,
            optimized_allocation=optimized_allocation,
            prior_total_acquisitions=round(prior_acq, 1),
            optimized_total_acquisitions=round(opt_acq, 1),
            lift_pct=lift_pct,
            model_diagnostics=ModelDiagnostics(
                r_hat_max=round(rng.uniform(1.001, 1.05), 3),
                ess_bulk_min=round(rng.uniform(450, 1200)),
                waic=round(rng.uniform(-4500, -3000), 1),
            ),
            model_fit=model_fit,
            contributions=contributions,
        )

        run_repo.save_results(run_id, results)
        set_progress(100, "completed")
        run_repo.update_status(run_id, RunStatus.completed, progress_pct=100)
        logger.info("fit_model_mock[%s]: completed. lift=%.1f%%", run_id, lift_pct)

    except Exception as exc:
        logger.exception("fit_model_mock[%s]: failed", run_id)
        from app.models.run import RunStatus
        run_repo.update_status(run_id, RunStatus.failed, error_message=str(exc))
        raise
