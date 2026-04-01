"""
Celery task: fit_model

Full MMM pipeline:
  1. Load raw CSV from Redis
  2. Fit Meridian model (long-running MCMC — blocks the Celery worker)
  3. Extract per-channel response curves from posterior samples
  4. Optimise budget allocation (scipy SLSQP)
  5. Assemble RunResults and persist to Redis
  6. Mark run as completed (or failed)
"""
from __future__ import annotations

import io
import logging

import pandas as pd

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.fit_model", max_retries=0)
def fit_model(self, payload: dict) -> None:
    """
    payload (JSON-serialised MMMJobPayload):
      run_id, session_id, upload_id, channel_names,
      total_budget, channel_constraints, meridian_config
    """
    run_id: str = payload["run_id"]
    upload_id: str = payload["upload_id"]
    channel_names: list[str] = payload["channel_names"]
    total_budget: float = payload["total_budget"]
    planning_period_label: str = payload.get("planning_period_label", "Quarterly")
    n_periods: int = payload.get("n_periods", 13)
    channel_constraints_raw: dict = payload.get("channel_constraints", {})
    meridian_config_raw: dict = payload.get("meridian_config", {})
    granularity: str = payload.get("granularity", "weekly")

    import redis as sync_redis
    from app.config import get_settings
    from app.models.run import ChannelConstraint, MeridianConfig, RunStatus
    from app.models.results import ModelDiagnostics, RunResults

    settings = get_settings()
    r = sync_redis.from_url(settings.REDIS_URL, decode_responses=False)
    run_repo = _SyncRunRepo(r, settings.SESSION_TTL_SECONDS)
    upload_repo = _SyncUploadRepo(r)

    def progress(pct: int, status: RunStatus = RunStatus.fitting) -> None:
        run_repo.update_status(run_id, status, progress_pct=pct)

    try:
        # ── Phase 1: load data ────────────────────────────────────────────
        progress(5)
        raw_csv = upload_repo.get_raw_csv(upload_id)
        if raw_csv is None:
            raise ValueError(f"Raw CSV not found for upload_id={upload_id}")
        df = pd.read_csv(io.BytesIO(raw_csv))
        logger.info("fit_model[%s]: CSV loaded (%d rows, channels=%s)", run_id, len(df), channel_names)

        # ── Phase 2: fit Meridian model ───────────────────────────────────
        progress(10)
        from app.mmm.meridian_wrapper import MeridianWrapper
        from app.models.run import MeridianConfig

        config = MeridianConfig(**meridian_config_raw)
        # Enforce minimum warmup — HMC needs enough steps to tune its step size.
        # With < 500 warmup on a multi-channel model, chains diverge and R-hat → ∞.
        MIN_WARMUP = 500
        if config.n_warmup < MIN_WARMUP:
            logger.warning(
                "fit_model[%s]: n_warmup=%d is below minimum %d — clamping.",
                run_id, config.n_warmup, MIN_WARMUP,
            )
            config = config.model_copy(update={"n_warmup": MIN_WARMUP})
        wrapper = MeridianWrapper(config)
        fit_result = wrapper.fit(
            df=df,
            channel_names=channel_names,
            granularity=granularity,
            progress_callback=lambda pct: progress(10 + int(pct * 0.7)),
        )
        logger.info("fit_model[%s]: model fitted. r_hat_max=%.3f", run_id, fit_result.r_hat_max)

        # ── Phase 3: response curves + time-series analytics ─────────────
        progress(82)
        from app.mmm.response_curves import extract_response_curves
        from app.mmm.model_analytics import extract_model_fit, extract_channel_contributions
        from app.models.results import ModelFitData, ContributionData

        response_curves = extract_response_curves(fit_result)

        fit_data_raw = extract_model_fit(fit_result.mmm, df, fit_result.kpi_scale)
        model_fit = ModelFitData(**fit_data_raw)

        contrib_raw = extract_channel_contributions(df, fit_result)
        contributions = ContributionData(**contrib_raw)

        # ── Phase 4: budget optimisation ──────────────────────────────────
        progress(88, RunStatus.optimizing)
        from app.mmm.budget_optimizer import (
            compute_prior_allocation,
            compute_total_acquisitions,
            optimize_budget,
        )
        from app.models.run import ChannelConstraint

        channel_constraints = {
            ch: ChannelConstraint(**v)
            for ch, v in channel_constraints_raw.items()
        }
        prior_allocation = compute_prior_allocation(df, channel_names, total_budget)
        optimized_allocation = optimize_budget(response_curves, total_budget, channel_constraints)

        prior_acq = compute_total_acquisitions(response_curves, prior_allocation)
        optimized_acq = compute_total_acquisitions(response_curves, optimized_allocation)
        lift_pct = ((optimized_acq - prior_acq) / prior_acq * 100) if prior_acq > 0 else 0.0

        # ── Phase 5: persist results ──────────────────────────────────────
        progress(95, RunStatus.optimizing)
        run_label = _get_run_label(r, run_id)
        results = RunResults(
            run_id=run_id,
            run_label=run_label,
            channels=channel_names,
            response_curves=response_curves,
            prior_allocation=prior_allocation,
            optimized_allocation=optimized_allocation,
            prior_total_acquisitions=prior_acq,
            optimized_total_acquisitions=optimized_acq,
            lift_pct=round(lift_pct, 2),
            model_diagnostics=ModelDiagnostics(
                r_hat_max=fit_result.r_hat_max,
                ess_bulk_min=fit_result.ess_bulk_min,
            ),
            planning_period_label=planning_period_label,
            n_periods=n_periods,
            model_fit=model_fit,
            contributions=contributions,
        )
        run_repo.save_results(run_id, results)
        run_repo.update_status(run_id, RunStatus.completed, progress_pct=100)
        logger.info("fit_model[%s]: completed. lift=%.1f%%", run_id, lift_pct)

    except Exception as exc:
        logger.exception("fit_model[%s]: failed", run_id)
        from app.models.run import RunStatus
        run_repo.update_status(run_id, RunStatus.failed, error_message=str(exc))
        raise


# ---------------------------------------------------------------------------
# Synchronous Redis helpers (Celery runs in a regular sync context)
# ---------------------------------------------------------------------------

def _get_run_label(r, run_id: str) -> str:
    from app.models.run import RunRecord
    raw = r.get(f"run:{run_id}")
    if raw:
        return RunRecord.model_validate_json(raw).run_label
    return run_id


class _SyncRunRepo:
    def __init__(self, client, ttl: int) -> None:
        self._r = client
        self._ttl = ttl

    def update_status(
        self,
        run_id: str,
        status,
        progress_pct: int | None = None,
        error_message: str | None = None,
    ) -> None:
        from datetime import datetime, timezone
        from app.models.run import RunRecord, RunStatus

        key = f"run:{run_id}"
        raw = self._r.get(key)
        if raw is None:
            return
        record = RunRecord.model_validate_json(raw)
        record.status = status
        if progress_pct is not None:
            record.progress_pct = progress_pct
        if error_message is not None:
            record.error_message = error_message
        if status in (RunStatus.completed, RunStatus.failed):
            record.completed_at = datetime.now(timezone.utc)
        self._r.set(key, record.model_dump_json(), ex=self._ttl)

    def save_results(self, run_id: str, results) -> None:
        self._r.set(f"run:{run_id}:results", results.model_dump_json(), ex=self._ttl)


class _SyncUploadRepo:
    def __init__(self, client) -> None:
        self._r = client

    def get_raw_csv(self, upload_id: str) -> bytes | None:
        return self._r.get(f"upload:{upload_id}:raw")
