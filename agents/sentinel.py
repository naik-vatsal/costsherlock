"""Sentinel Agent — detects cost anomalies using z-score over a rolling window."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from agents import Anomaly

logger = logging.getLogger(__name__)


class Sentinel:
    """Agent 1: Detects cost anomalies from AWS Cost Explorer JSON exports.

    Uses a rolling z-score approach: for each service, computes a rolling
    mean and standard deviation over a configurable window. Any day whose
    cost deviates by more than *z_threshold* standard deviations is flagged.
    """

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    @staticmethod
    def load_from_json(filepath: str | Path) -> pd.DataFrame:
        """Load a Cost Explorer JSON export into a tidy DataFrame.

        Args:
            filepath: Path to a JSON file containing a list of records with
                keys ``date`` (ISO-8601 string), ``service`` (str), and
                ``cost`` (numeric).

        Returns:
            DataFrame with columns [date, service, cost] where ``date`` is
            a ``datetime64[ns]`` column sorted ascending.

        Raises:
            FileNotFoundError: If *filepath* does not exist.
            ValueError: If required keys are missing from any record.
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Cost export not found: {filepath}")

        with filepath.open() as fh:
            records: list[dict] = json.load(fh)

        required = {"date", "service", "cost"}
        for i, rec in enumerate(records):
            missing = required - rec.keys()
            if missing:
                raise ValueError(
                    f"Record {i} is missing required keys: {missing}"
                )

        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df["cost"] = df["cost"].astype(float)
        df.sort_values("date", inplace=True)
        df.reset_index(drop=True, inplace=True)

        logger.info(
            "Loaded %d records spanning %s → %s for %d services",
            len(df),
            df["date"].min().date(),
            df["date"].max().date(),
            df["service"].nunique(),
        )
        return df

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_anomalies(
        df: pd.DataFrame,
        window: int = 14,
        z_threshold: float = 2.5,
    ) -> list[Anomaly]:
        """Detect cost anomalies per service using a rolling z-score.

        For each service the rolling mean and standard deviation are
        computed over *window* days (minimum periods = *window*).  A day
        is flagged when ``(cost - mean) / std > z_threshold``.

        Edge cases handled:
        * Fewer than *window* days of data for a service → skipped entirely.
        * Rolling std equals zero (flat costs) → the z-score is undefined;
          those rows are skipped.

        Args:
            df: DataFrame produced by :meth:`load_from_json` with columns
                [date, service, cost].
            window: Size of the rolling window in days (default 14).
            z_threshold: Minimum z-score to flag as anomalous (default 2.5).

        Returns:
            List of :class:`~agents.Anomaly` instances sorted by
            ``z_score`` descending.
        """
        anomalies: list[Anomaly] = []

        for service, grp in df.groupby("service"):
            grp = grp.sort_values("date").reset_index(drop=True)

            if len(grp) < window:
                logger.debug(
                    "Skipping '%s': only %d days (need %d)",
                    service,
                    len(grp),
                    window,
                )
                continue

            rolling = grp["cost"].rolling(window=window, min_periods=window)
            grp = grp.copy()
            grp["rolling_mean"] = rolling.mean()
            grp["rolling_std"] = rolling.std()

            # Rows where rolling stats are available
            valid = grp.dropna(subset=["rolling_mean", "rolling_std"])

            # Skip rows with zero std (no variation → z-score undefined)
            valid = valid[valid["rolling_std"] > 0]

            valid = valid.copy()
            valid["z_score"] = (
                (valid["cost"] - valid["rolling_mean"]) / valid["rolling_std"]
            )

            flagged = valid[valid["z_score"] > z_threshold]

            for _, row in flagged.iterrows():
                anomaly = Anomaly(
                    service=str(service),
                    date=row["date"].strftime("%Y-%m-%d"),
                    cost=round(float(row["cost"]), 4),
                    expected_cost=round(float(row["rolling_mean"]), 4),
                    z_score=round(float(row["z_score"]), 4),
                    delta=round(float(row["cost"] - row["rolling_mean"]), 4),
                )
                anomalies.append(anomaly)
                logger.info(
                    "Anomaly detected: %s on %s — cost $%.2f, z=%.2f",
                    service,
                    anomaly.date,
                    anomaly.cost,
                    anomaly.z_score,
                )

        anomalies.sort(key=lambda a: a.z_score, reverse=True)
        logger.info(
            "Detection complete: %d anomalies found across %d services",
            len(anomalies),
            df["service"].nunique(),
        )
        return anomalies
