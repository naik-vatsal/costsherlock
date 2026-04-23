"""Tests for agents.sentinel.Sentinel."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from agents import Anomaly
from agents.sentinel import Sentinel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEMO_JSON = Path(__file__).parent.parent / "data" / "synthetic" / "demo_cost.json"


def _write_json(records: list[dict], tmp_path: Path) -> Path:
    """Write records to a temp JSON file and return its path."""
    p = tmp_path / "costs.json"
    p.write_text(json.dumps(records))
    return p


def _flat_records(service: str, n: int, cost: float = 10.0) -> list[dict]:
    """Generate *n* days of flat cost records for a single service."""
    from datetime import date, timedelta

    start = date(2026, 1, 1)
    return [
        {"date": (start + timedelta(days=i)).isoformat(), "service": service, "cost": cost}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# load_from_json
# ---------------------------------------------------------------------------


class TestLoadFromJson:
    def test_loads_demo_file(self):
        df = Sentinel.load_from_json(DEMO_JSON)
        assert not df.empty
        assert set(df.columns) >= {"date", "service", "cost"}

    def test_date_column_is_datetime(self):
        df = Sentinel.load_from_json(DEMO_JSON)
        import pandas as pd
        assert pd.api.types.is_datetime64_any_dtype(df["date"])

    def test_sorted_ascending(self):
        df = Sentinel.load_from_json(DEMO_JSON)
        assert df["date"].is_monotonic_increasing

    def test_missing_key_raises(self, tmp_path):
        bad = [{"date": "2026-01-01", "cost": 10.0}]  # missing 'service'
        p = _write_json(bad, tmp_path)
        with pytest.raises(ValueError, match="service"):
            Sentinel.load_from_json(p)

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            Sentinel.load_from_json("/nonexistent/path/costs.json")


# ---------------------------------------------------------------------------
# detect_anomalies — injected anomalies
# ---------------------------------------------------------------------------


class TestKnownAnomalies:
    """The three injected spikes must be detected."""

    @pytest.fixture(scope="class")
    def anomalies(self):
        df = Sentinel.load_from_json(DEMO_JSON)
        return Sentinel.detect_anomalies(df)

    def _find(self, anomalies: list[Anomaly], service: str, date: str) -> Anomaly | None:
        return next(
            (a for a in anomalies if a.service == service and a.date == date), None
        )

    def test_ec2_spike_detected(self, anomalies):
        hit = self._find(anomalies, "Amazon EC2", "2026-01-30")
        assert hit is not None, "EC2 spike on 2026-01-30 not detected"
        assert hit.z_score > 2.5

    def test_s3_spike_detected(self, anomalies):
        hit = self._find(anomalies, "Amazon S3", "2026-02-04")
        assert hit is not None, "S3 spike on 2026-02-04 not detected"
        assert hit.z_score > 2.5

    def test_cloudwatch_spike_detected(self, anomalies):
        hit = self._find(anomalies, "Amazon CloudWatch", "2026-02-07")
        assert hit is not None, "CloudWatch spike on 2026-02-07 not detected"
        assert hit.z_score > 2.5

    def test_sorted_by_z_score_descending(self, anomalies):
        scores = [a.z_score for a in anomalies]
        assert scores == sorted(scores, reverse=True)

    def test_anomaly_fields_populated(self, anomalies):
        for a in anomalies:
            assert a.service
            assert a.date
            assert a.cost > 0
            assert a.expected_cost > 0
            assert a.delta == pytest.approx(a.cost - a.expected_cost, abs=1e-3)


# ---------------------------------------------------------------------------
# detect_anomalies — normal days NOT flagged
# ---------------------------------------------------------------------------


class TestNormalDaysNotFlagged:
    def test_no_false_positives_rds(self):
        """RDS has no injected spikes; no anomalies expected."""
        df = Sentinel.load_from_json(DEMO_JSON)
        anomalies = Sentinel.detect_anomalies(df)
        rds_hits = [a for a in anomalies if a.service == "Amazon RDS"]
        assert rds_hits == [], f"Unexpected RDS anomalies: {rds_hits}"

    def test_no_false_positives_lambda(self):
        """Lambda has no injected spikes; no anomalies expected."""
        df = Sentinel.load_from_json(DEMO_JSON)
        anomalies = Sentinel.detect_anomalies(df)
        lambda_hits = [a for a in anomalies if a.service == "AWS Lambda"]
        assert lambda_hits == [], f"Unexpected Lambda anomalies: {lambda_hits}"

    def test_perfectly_flat_not_flagged(self, tmp_path):
        """Perfectly flat costs → rolling std = 0 → no anomalies."""
        records = _flat_records("FlatService", n=30, cost=50.0)
        p = _write_json(records, tmp_path)
        df = Sentinel.load_from_json(p)
        anomalies = Sentinel.detect_anomalies(df)
        assert anomalies == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_all_zero_costs(self, tmp_path):
        """All-zero costs → std = 0 for all windows → no anomalies."""
        records = _flat_records("ZeroService", n=30, cost=0.0)
        p = _write_json(records, tmp_path)
        df = Sentinel.load_from_json(p)
        anomalies = Sentinel.detect_anomalies(df)
        assert anomalies == []

    def test_single_day_of_data(self, tmp_path):
        """Only one record → fewer than window days → skipped, no anomalies."""
        records = [{"date": "2026-01-01", "service": "Tiny", "cost": 9999.0}]
        p = _write_json(records, tmp_path)
        df = Sentinel.load_from_json(p)
        anomalies = Sentinel.detect_anomalies(df)
        assert anomalies == []

    def test_exactly_window_minus_one_days_skipped(self, tmp_path):
        """window-1 days of data → skipped entirely."""
        records = _flat_records("AlmostEnough", n=13, cost=100.0)
        # Spike on last day — should still be skipped
        records[-1]["cost"] = 9999.0
        p = _write_json(records, tmp_path)
        df = Sentinel.load_from_json(p)
        anomalies = Sentinel.detect_anomalies(df, window=14)
        assert anomalies == []

    def test_custom_threshold(self, tmp_path):
        """A spike that clears z=2.5 but not z=10 should not appear at high threshold.

        Uses deterministic alternating costs so the rolling std is ~2.0 and the
        spike of +14 yields z ≈ 7 (clearly > 2.5, clearly < 10).
        """
        from datetime import date, timedelta

        start = date(2026, 1, 1)
        records = []
        # Alternating 48 / 52 → mean=50, std≈2 for any window of ≥2 days
        for i in range(30):
            cost = 48.0 if i % 2 == 0 else 52.0
            records.append(
                {"date": (start + timedelta(days=i)).isoformat(), "service": "S", "cost": cost}
            )
        # Spike: mean≈50, std≈2.05 → z ≈ (64-50)/2.05 ≈ 6.8 (> 2.5, < 10)
        records.append({"date": "2026-01-31", "service": "S", "cost": 64.0})

        p = _write_json(records, tmp_path)
        df = Sentinel.load_from_json(p)

        found_at_2_5 = Sentinel.detect_anomalies(df, z_threshold=2.5)
        found_at_10 = Sentinel.detect_anomalies(df, z_threshold=10.0)

        assert len(found_at_2_5) >= 1
        assert len(found_at_10) == 0

    def test_returns_anomaly_model_instances(self, tmp_path):
        """Return type must be list[Anomaly]."""
        df = Sentinel.load_from_json(DEMO_JSON)
        anomalies = Sentinel.detect_anomalies(df)
        assert all(isinstance(a, Anomaly) for a in anomalies)
