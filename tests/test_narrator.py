"""Tests for agents.narrator.Narrator.

The integration test makes a live Claude API call; the unit test for the
inference tagger runs entirely offline.
"""

from __future__ import annotations

import pytest

from agents import Anomaly, Hypothesis, RuledOutEvent
from agents.narrator import Narrator, REQUIRED_SECTIONS, _tag_uncited_claims


# ---------------------------------------------------------------------------
# Shared mock analysis fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mock_analysis() -> dict:
    """Realistic Analyst output for an EC2 compute spike."""
    return {
        "hypotheses": [
            Hypothesis(
                rank=1,
                root_cause=(
                    "20 c5.2xlarge instances launched by deploy-bot at "
                    "2026-01-29T23:15Z ran continuously through the anomaly date, "
                    "generating $163.20/day in on-demand compute charges."
                ),
                confidence=0.92,
                evidence=[
                    "CloudTrail event [ec2-test-001] at 2026-01-29T23:15:00Z: "
                    "RunInstances launched 20x c5.2xlarge by deploy-bot",
                    "Pricing doc [ec2_ondemand_pricing.md]: c5.2xlarge costs $0.340/hr",
                ],
                cost_calculation=(
                    "20 instances × $0.340/hr × 24 hrs = $163.20/day "
                    "vs observed delta $336.03/day (49% of delta explained by "
                    "compute; remaining from EBS, data transfer, and partial-day billing)"
                ),
                causal_mechanism=(
                    "RunInstances creates new EC2 instances that bill at the "
                    "on-demand hourly rate from the moment they enter 'running' state. "
                    "20 c5.2xlarge instances at $0.340/hr each represent $6.80/hr of "
                    "additional ongoing cost that compounds over the full anomaly day."
                ),
                category="compute_overprovisioning",
            )
        ],
        "ruled_out": [
            RuledOutEvent(
                event_name="ModifyInstanceAttribute",
                event_time="2026-01-30T08:20:00Z",
                reason=(
                    "ModifyInstanceAttribute for 'userData' only changes the boot "
                    "script metadata. It does not create new instances, change instance "
                    "type, or affect the per-hour billing rate."
                ),
                category="WRONG_MECHANISM",
            ),
            RuledOutEvent(
                event_name="StopInstances",
                event_time="2026-01-28T14:30:00Z",
                reason=(
                    "StopInstances on 2x t3.micro ($0.0104/hr each) saves at most "
                    "$0.50/day — cannot explain a $336 spike. Opposite causal direction."
                ),
                category="WRONG_MAGNITUDE",
            ),
        ],
    }


@pytest.fixture(scope="module")
def mock_anomaly() -> Anomaly:
    return Anomaly(
        service="Amazon EC2",
        date="2026-01-30",
        cost=413.72,
        expected_cost=77.69,
        z_score=3.47,
        delta=336.03,
    )


# ---------------------------------------------------------------------------
# Unit test — inference tagger (no API call)
# ---------------------------------------------------------------------------

def test_inference_tagger_adds_tag_to_uncited_claim() -> None:
    """Lines with cost figures but no citation should get [INFERENCE] prefix."""
    text = (
        "## Executive Summary\n"
        "The service cost $500 more than expected.\n"          # uncited claim → tag
        "This was caused by new instances. [CloudTrail: abc]\n"  # has citation → no tag
        "A 40% increase was observed.\n"                         # uncited pct → tag
        "## Ruled Out\n"
        "| Event | Reason |\n"
        "| --- | --- |\n"
        "| RunInstances | cost spike |\n"                        # table row → skip
    )
    result = _tag_uncited_claims(text)
    lines = result.splitlines()

    assert lines[1].startswith("[INFERENCE]"), "Dollar-amount line should be tagged"
    assert not lines[2].startswith("[INFERENCE]"), "Cited line should not be tagged"
    assert lines[3].startswith("[INFERENCE]"), "Percentage line should be tagged"
    # Table row must not be mangled
    assert "|" in lines[6], "Table row should pass through unchanged"


def test_inference_tagger_leaves_clean_report_untouched() -> None:
    """A fully cited report should receive zero [INFERENCE] tags."""
    text = (
        "## Executive Summary\n"
        "Costs rose by $336 [CloudTrail: evt-001].\n"
        "The c5.2xlarge rate is $0.340/hr [Pricing: ec2_ondemand_pricing.md].\n"
        "## Evidence Chain\n"
        "1. 20 instances launched [CloudTrail: evt-001]\n"
    )
    result = _tag_uncited_claims(text)
    assert "[INFERENCE]" not in result, "Fully cited report should have no inference tags"


# ---------------------------------------------------------------------------
# Integration test — full report generation
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_report_contains_all_sections(
    mock_anomaly: Anomaly,
    mock_analysis: dict,
) -> None:
    """Generated report must contain all 7 required section headers."""
    narrator = Narrator()
    report = narrator.generate_report(mock_anomaly, mock_analysis)

    assert isinstance(report, str) and len(report) > 200, (
        "Report should be a non-empty markdown string"
    )

    missing = [s for s in REQUIRED_SECTIONS if s not in report]
    assert not missing, (
        f"Report is missing {len(missing)} required section(s): {missing}\n\n"
        f"Report preview:\n{report[:600]}"
    )
