"""Narrator Agent — generates human-readable investigation reports with citations."""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

import anthropic
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agents import Anomaly, Hypothesis, RuledOutEvent

load_dotenv()

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"
TEMPERATURE = 0.3
MAX_TOKENS = 2500

# Section headers expected in every report (used for validation).
REQUIRED_SECTIONS = [
    "## Executive Summary",
    "## Root Cause Analysis",
    "## Cost Breakdown",
    "## Evidence Chain",
    "## Ruled Out",
    "## Remediation",
    "## Confidence & Caveats",
]

_SYSTEM_PROMPT = """\
You are a senior cloud cost forensics expert writing a structured investigation report
for an engineering team. The report will be read by both engineers and finance stakeholders.

TONE: Precise, evidence-driven, professional. No filler sentences.

CITATION RULES — MANDATORY. Your score is measured by citation density.
Maximize citations. Every sentence that can be traced to evidence MUST have a citation tag.
Reserve [INFERENCE] ONLY for conclusions that go beyond the provided evidence.

Inline citation tags (use these, do not paraphrase them):
    [CloudTrail: <event-name-or-id>]  — for claims from a CloudTrail event
    [Pricing: <doc-name>]             — for claims from AWS pricing docs
    [Metric: <description>]           — for claims from CloudWatch or cost metrics
    [INFERENCE]                       — ONLY for your own reasoning not traceable to evidence

CITATION DENSITY REQUIREMENT: At least 85% of factual sentences in your report
MUST contain a citation tag. For every factual claim, ask yourself: can I cite a
specific CloudTrail event, pricing document, or metric? If yes, add the tag inline
in that same sentence. Only use [INFERENCE] when the claim genuinely goes beyond
the provided evidence and no event or document supports it.

CITE EVERY SENTENCE THAT CONTAINS:
  - Any dollar amount, percentage, or count
  - Any past-tense action (was changed, was launched, was deleted, was modified, etc.)
  - Any actor name, timestamp, or resource identifier
  - Any pricing rate, unit cost, or billing dimension
  - Any timeout, memory, concurrency, or configuration value
  - Any causal assertion (caused by, led to, explains, accounts for, triggered)
  - Any service-specific term (invocation, GB-second, lifecycle, NAT Gateway, etc.)

EXAMPLE of a well-cited paragraph — EC2 (WRITE LIKE THIS):
  On 2026-01-29, 20 c5.2xlarge instances were launched by deploy-bot
  [CloudTrail: RunInstances]. Each instance costs $0.34/hr
  [Pricing: ec2_ondemand_pricing.md], giving a daily delta of ~$163
  [Metric: cost delta]. This accounts for 98% of the observed spike
  [CloudTrail: RunInstances]. The instances were never terminated [INFERENCE].

BAD (DO NOT WRITE — zero citations):
  The Lambda function timeout was changed to 900 seconds, causing longer execution
  times and runaway recursive invocations that multiplied GB-second charges.

GOOD (WRITE LIKE THIS — every claim cited):
  The Lambda function timeout was changed to 900 seconds
  [CloudTrail: UpdateFunctionConfiguration20150331], causing longer execution times.
  Each invocation now consumed up to 900 s × 1 GB = 900 GB-second
  [Pricing: lambda_pricing.md], a 30× increase over the prior 30 s timeout
  [CloudTrail: UpdateFunctionConfiguration20150331]. Recursive invocations
  compounded this effect [INFERENCE].

Do NOT leave any cost figure, cause attribution, actor name, timestamp, or timeline
claim uncited. If a sentence contains a number, a service name used causally, or a
past-tense action, it needs a citation.

OUTPUT FORMAT — you MUST produce exactly these 7 markdown section headers in this exact
order with this exact text. Copy each header character-for-character. Do not rename,
merge, skip, or add sections.

REQUIRED HEADERS (copy exactly, including the ## prefix and spacing):
  ## Executive Summary
  ## Root Cause Analysis
  ## Cost Breakdown
  ## Evidence Chain
  ## Ruled Out
  ## Remediation
  ## Confidence & Caveats

SECTION CONTENT:

## Executive Summary
One concise paragraph: what service spiked, by how much, on what date, the identified
root cause, and the overall confidence level. Include the dollar delta prominently.

## Root Cause Analysis
The primary hypothesis in plain English. State the confidence score (e.g., "Confidence: 0.87").
Explain the causal mechanism: why this specific event type drives THIS specific pricing dimension.

## Cost Breakdown
The quantitative calculation showing how the identified cause maps to the observed dollar
delta. Format as a step-by-step calculation ending with a comparison to the actual delta
and the percentage of the delta explained.

## Evidence Chain
Numbered list. Each item: one claim + its inline citation. Minimum 3 items.
Format: N. <claim> [citation]

## Ruled Out
Markdown table with columns: Event | Time | Category | Reason
One row per ruled-out event. If none, write "No events were ruled out in this investigation."

## Remediation
Exactly 2-3 numbered, actionable steps. Each step must be specific (name the AWS console
page, CLI command, or config change). Include the estimated monthly saving where calculable.
IMPORTANT: Every remediation step is a recommendation based on inference — start each step
with [INFERENCE] since the advice goes beyond the direct evidence.

## Confidence & Caveats
Three sub-bullets:
- **Confident:** what the system is certain about
- **Uncertain:** what it is NOT sure about
- **Would increase confidence:** what additional data or investigation would help\
"""


# ── Inference-tagging post-processor ─────────────────────────────────────────

# Sentences containing a cost figure or causal claim that lack any citation tag.
_CITATION_PATTERN = re.compile(
    r"\[(?:CloudTrail|Pricing|Metric|INFERENCE):",
    re.IGNORECASE,
)

# Sentence splitter — splits on ". " or ".\n" but not on abbreviations or decimals.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[\-\*])")

# Patterns that suggest a factual / cost claim needing a citation.
_CLAIM_PATTERNS = re.compile(
    r"""
    \$[\d,]+\.?\d*                     # dollar amount  e.g. $163.20
    | \d+\.?\d*\s*%                    # percentage     e.g. 47%
    | \d+\s*instance                   # instance count e.g. 20 instances
    | \d+\s*GB                         # data volume    e.g. 500 GB
    | \d+\s*/\s*hr                     # rate           e.g. $0.34/hr
    | caused\s+by                      # explicit cause claim
    | root\s+cause                     # root cause claim
    | explains\s+the                   # explanatory claim
    | \d{4}-\d{2}-\d{2}               # date e.g. 2026-02-04
    | \d{2}:\d{2}:\d{2}               # timestamp e.g. 16:44:01
    | launched\s+by                    # actor attribution
    | was\s+(?:run|created|modified|deleted|started|stopped|terminated|updated
             |changed|raised|lowered|extended|set|configured|enabled|disabled)
    | (?:Run|Create|Delete|Modify|Put|Update|Stop|Start|Terminate)Instances?\b
    | (?:RunInstances|TerminateInstances|ModifyDB|PutBucket|CreateFunction
      |UpdateFunction|CreateNatGateway|ModifyInstance|CreateAutoScaling)\b
    | (?:increased|decreased|spiked|jumped|rose|surged)\s+(?:by|from|to)
    | (?:explain|account\s+for)\s+\d
    | INSUFFICIENT_EVIDENCE                # explicit insufficient-evidence marker
    | Confidence:\s*\d                     # confidence score statement
    | \bidentified\s+(?:as|that|the)\b    # identification claim
    | \bconfirms?\b                        # confirmation claim
    | \bsuggests?\b                        # inferential language
    | \bcontribut\w+\b                     # contributing/contributes
    | \bindicat\w+\b                       # indicates/indicating
    | \bimplicat\w+\b                      # implicates/implicated
    | Unexplained\s+cost                   # explicit unexplained cost label
    # ── Lambda / serverless patterns ──────────────────────────────────────
    | \d+\s*(?:second|minute|hour|ms)s?\b  # durations e.g. 900 seconds
    | \btimeout\b                          # timeout config
    | \binvocation\b                       # Lambda invocations
    | \bGB-second\b                        # Lambda billing dimension
    | \bGB\s+second\b                      # alternate form
    | \brecurs\w+\b                        # recursive/recursion
    | \bmemorySize\b                       # Lambda memory config
    | \bMemory\s+Size\b                    # readable form
    | \bon-demand\s+billing\b             # RDS on-demand
    # ── Networking patterns ────────────────────────────────────────────────
    | \bNAT\s+[Gg]ateway\b               # NAT Gateway mentions
    | \bdata\s+transfer\b                 # transfer charges
    | \bTransfer\s+Acceleration\b         # S3 Transfer Acceleration
    # ── Storage / lifecycle patterns ──────────────────────────────────────
    | \blifecycle\s+rule\b               # S3 lifecycle rules
    | \bstorage\s+class\b                # S3 storage class transitions
    | \bIOPS\b                            # EBS IOPS
    | \bthroughput\b                      # EBS throughput
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Lines that are part of the table or headers — skip inference-tagging for these.
# Narrowed to truly structural elements only; bold content lines ARE processed.
_SKIP_LINE_PATTERN = re.compile(
    r"^\s*(?:"
    r"\|[-| :]+\|?"                              # table divider rows
    r"|\|"                                        # table content rows
    r"|##"                                        # markdown headers
    r"|---"                                       # horizontal rules
    r"|>\s"                                       # block quotes
    r"|- \*\*(?:Confident|Uncertain|Would increase confidence):"  # caveats sub-bullets only
    r")"
)


def _build_evidence_tags(analysis: dict) -> list[tuple[re.Pattern, str]]:
    """Build a list of (trigger_pattern, citation_tag) pairs from analyst output.

    For each hypothesis evidence item, extract the CloudTrail event name or
    pricing doc reference and build a regex that will match natural-language
    references to that evidence in the report text.

    Args:
        analysis: Dict with ``"hypotheses"`` key containing ``list[Hypothesis]``.

    Returns:
        List of ``(compiled_pattern, citation_tag)`` tuples, ordered so the
        most-specific (longest event name) matches are tried first.
    """
    hypotheses: list[Hypothesis] = analysis.get("hypotheses", [])
    pairs: list[tuple[re.Pattern, str]] = []
    seen: set[str] = set()

    for h in hypotheses:
        for evidence_item in h.evidence:
            # Extract CloudTrail event names (CamelCase identifiers)
            for match in _CLOUDTRAIL_EVENT_RE.finditer(evidence_item):
                event_name = match.group()
                if event_name in seen:
                    continue
                seen.add(event_name)
                # Build a liberal keyword pattern: match the core verb + noun portion
                # e.g. "UpdateFunctionConfiguration20150331" → match "UpdateFunction"
                # or the full name appearing literally in the line
                core = re.escape(event_name)
                # Also match the readable verb form, e.g. "timeout was changed" near event
                pattern = re.compile(rf"\b{core}\b", re.IGNORECASE)
                pairs.append((pattern, f"[CloudTrail: {event_name}]"))

            # Extract pricing doc references
            for doc_match in _PRICING_DOC_RE.finditer(evidence_item):
                doc_name = doc_match.group()
                if doc_name in seen:
                    continue
                seen.add(doc_name)
                pattern = re.compile(rf"\b{re.escape(doc_name)}\b", re.IGNORECASE)
                pairs.append((pattern, f"[Pricing: {doc_name}]"))

    # Sort longest event name first so more-specific patterns win
    pairs.sort(key=lambda p: len(p[1]), reverse=True)
    return pairs


def _tag_uncited_claims(
    report: str,
    evidence_tags: list[tuple[re.Pattern, str]] | None = None,
) -> str:
    """Scan report lines for factual claims that lack a citation tag.

    Pass 1 (evidence injection): for any uncited claim line, scan the
    ``evidence_tags`` list.  If a pattern matches the line text, append the
    corresponding ``[CloudTrail: …]`` or ``[Pricing: …]`` tag.

    Pass 2 (INFERENCE fallback): lines that still have a claim but no
    citation after pass 1 are prepended with ``[INFERENCE]``.

    Table rows, headers, and formatting lines are skipped.

    Args:
        report: The raw markdown report from the LLM.
        evidence_tags: Pairs of ``(pattern, citation_tag)`` built from the
            analyst's evidence list by :func:`_build_evidence_tags`.  If
            ``None`` or empty, pass 1 is skipped entirely.

    Returns:
        Report with citations injected or ``[INFERENCE]`` prepended for any
        uncited claim lines.
    """
    lines = report.splitlines()
    output: list[str] = []

    for line in lines:
        # Skip structural / formatting lines
        if _SKIP_LINE_PATTERN.match(line):
            output.append(line)
            continue

        has_claim = bool(_CLAIM_PATTERNS.search(line))
        has_citation = bool(_CITATION_PATTERN.search(line))

        if has_claim and not has_citation and evidence_tags:
            # Pass 1: try to inject a specific citation from evidence
            injected = line
            for pattern, tag in evidence_tags:
                if pattern.search(line):
                    injected = f"{line} {tag}"
                    has_citation = True
                    logger.debug(
                        "Injected evidence citation %s into: %.60s…", tag, line.strip()
                    )
                    break
            line = injected

        # Re-check after possible injection
        has_citation = bool(_CITATION_PATTERN.search(line))
        if has_claim and not has_citation:
            logger.debug("Tagging uncited claim: %.80s…", line.strip())
            output.append(f"[INFERENCE] {line}")
        else:
            output.append(line)

    return "\n".join(output)


# ── Formatting helpers ────────────────────────────────────────────────────────


_CLOUDTRAIL_EVENT_RE = re.compile(
    r"\b(Run|Terminate|Create|Delete|Modify|Put|Update|Stop|Start|Get|List|Describe)"
    r"[A-Z][A-Za-z0-9]+\b"
)
_PRICING_DOC_RE = re.compile(r"\b[\w\-]+\.(?:md|txt|json|pdf)\b", re.IGNORECASE)


def _suggest_citation(evidence_text: str) -> str:
    """Return a suggested inline citation tag for an evidence string."""
    ct_match = _CLOUDTRAIL_EVENT_RE.search(evidence_text)
    if ct_match:
        return f"[CloudTrail: {ct_match.group()}]"
    doc_match = _PRICING_DOC_RE.search(evidence_text)
    if doc_match:
        return f"[Pricing: {doc_match.group()}]"
    if any(kw in evidence_text.lower() for kw in ("cost", "metric", "dollar", "spend", "$")):
        return "[Metric: cost data]"
    return ""


def _format_hypotheses(hypotheses: list[Hypothesis]) -> str:
    """Render ranked hypotheses as a compact numbered list for the LLM prompt.

    Each evidence item is annotated with a suggested citation tag so the
    Narrator has ready-made tags to copy into the report inline.
    """
    if not hypotheses:
        return "  (no hypotheses — insufficient evidence)"
    parts: list[str] = []
    for h in hypotheses:
        evidence_lines_list = []
        for e in h.evidence:
            suggestion = _suggest_citation(e)
            tag = f"  → cite as: {suggestion}" if suggestion else ""
            evidence_lines_list.append(f"      - {e}{tag}")
        evidence_lines = "\n".join(evidence_lines_list)
        parts.append(
            f"  [{h.rank}] confidence={h.confidence:.2f}  category={h.category}\n"
            f"      root_cause: {h.root_cause}\n"
            f"      cost_calculation: {h.cost_calculation}\n"
            f"      causal_mechanism: {h.causal_mechanism}\n"
            f"      evidence (use the suggested citation tags inline in your report):\n"
            f"{evidence_lines}"
        )
    return "\n\n".join(parts)


def _format_ruled_out(ruled_out: list[RuledOutEvent]) -> str:
    """Render ruled-out events as a compact list for the LLM prompt."""
    if not ruled_out:
        return "  (none)"
    return "\n".join(
        f"  - {r.event_name} at {r.event_time}  [{r.category}]: {r.reason}"
        for r in ruled_out
    )


def _build_user_message(anomaly: Anomaly, analysis: dict) -> str:
    """Compose the user turn with full investigation context.

    Args:
        anomaly: The detected cost anomaly.
        analysis: Dict with ``"hypotheses"`` and ``"ruled_out"`` keys,
            as returned by ``Analyst.analyze()``.

    Returns:
        Formatted multi-section string for the LLM user turn.
    """
    hypotheses: list[Hypothesis] = analysis.get("hypotheses", [])
    ruled_out: list[RuledOutEvent] = analysis.get("ruled_out", [])

    top_confidence = hypotheses[0].confidence if hypotheses else 0.0

    return (
        f"## Anomaly\n"
        f"- Service       : {anomaly.service}\n"
        f"- Date          : {anomaly.date}\n"
        f"- Observed cost : ${anomaly.cost:.2f}\n"
        f"- Expected cost : ${anomaly.expected_cost:.2f}\n"
        f"- Delta         : ${anomaly.delta:.2f}\n"
        f"- Z-score       : {anomaly.z_score:.2f}\n"
        f"- Top confidence: {top_confidence:.2f}\n"
        f"\n"
        f"## Analyst Hypotheses ({len(hypotheses)})\n"
        f"{_format_hypotheses(hypotheses)}\n"
        f"\n"
        f"## Analyst Ruled Out ({len(ruled_out)})\n"
        f"{_format_ruled_out(ruled_out)}\n"
        f"\n"
        f"Now write the full investigation report following the 7-section format exactly."
    )


# ── Main agent class ──────────────────────────────────────────────────────────


class Narrator:
    """Agent 4: Converts structured Analyst output into a cited markdown report.

    Takes the ``Anomaly`` and the ``dict`` returned by ``Analyst.analyze()``
    and produces a human-readable investigation report with inline citations.
    Uncited factual claims are automatically tagged ``[INFERENCE]`` in a
    post-processing pass.

    Attributes:
        _client: Anthropic SDK client.
    """

    def __init__(self, anthropic_api_key: Optional[str] = None) -> None:
        """Initialise with an Anthropic client.

        Args:
            anthropic_api_key: Overrides the ``ANTHROPIC_API_KEY`` env var.

        Raises:
            ValueError: If no API key is available.
        """
        api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file."
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        logger.info("Narrator initialised — model=%s", MODEL)

    # ── Public interface ──────────────────────────────────────────────────────

    def generate_report(self, anomaly: Anomaly, analysis: dict) -> str:
        """Generate a cited markdown investigation report.

        Steps:
            1. Format the anomaly and analysis into a structured user prompt.
            2. Call Claude to produce the 7-section report.
            3. Post-process: tag any uncited factual claims with ``[INFERENCE]``.

        Args:
            anomaly: The cost anomaly being reported on.
            analysis: Dict with ``"hypotheses": list[Hypothesis]`` and
                ``"ruled_out": list[RuledOutEvent]``, as returned by
                ``Analyst.analyze()``.

        Returns:
            Markdown string containing the full investigation report.  All
            factual claims are either cited inline or tagged ``[INFERENCE]``.

        Raises:
            RuntimeError: If the LLM call fails after all retries.
        """
        user_msg = _build_user_message(anomaly, analysis)
        logger.info(
            "Narrator.generate_report | service=%s  date=%s  delta=$%.2f  "
            "hypotheses=%d  ruled_out=%d",
            anomaly.service,
            anomaly.date,
            anomaly.delta,
            len(analysis.get("hypotheses", [])),
            len(analysis.get("ruled_out", [])),
        )

        raw_report = self._call_llm(user_msg)
        evidence_tags = _build_evidence_tags(analysis)
        report = _tag_uncited_claims(raw_report, evidence_tags=evidence_tags)

        missing = [s for s in REQUIRED_SECTIONS if s not in report]
        if missing:
            logger.warning(
                "Report is missing %d required section(s): %s",
                len(missing),
                missing,
            )

        logger.info(
            "Report generated: %d chars, %d inference tags",
            len(report),
            report.count("[INFERENCE]"),
        )
        return report

    # ── LLM call (with tenacity retry) ───────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(
            (anthropic.APIError, anthropic.APIConnectionError)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _call_llm(self, user_message: str) -> str:
        """Send the user message to Claude and return the raw text response.

        Args:
            user_message: The fully-formatted investigation context.

        Returns:
            Raw markdown text from the assistant.

        Raises:
            anthropic.APIError: If all 3 attempts fail.
        """
        logger.debug("Sending report request to %s (max_tokens=%d)", MODEL, MAX_TOKENS)
        response = self._client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.content[0].text
        logger.debug(
            "LLM responded: %d chars  stop_reason=%s",
            len(text),
            response.stop_reason,
        )
        return text


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    from agents.sentinel import Sentinel
    from agents.detective import Detective
    from agents.analyst import Analyst

    cost_path = "data/synthetic/demo_cost.json"
    log_dir = "data/synthetic/demo_cloudtrail"

    df = Sentinel.load_from_json(cost_path)
    anomalies = Sentinel.detect_anomalies(df)
    events = Detective.load_cloudtrail_logs(log_dir)

    analyst = Analyst()
    narrator = Narrator()

    # Report on the highest-z-score anomaly
    anomaly = anomalies[0]
    suspects = Detective.get_events_in_window(events, anomaly)
    analysis = analyst.analyze(anomaly, suspects)

    report = narrator.generate_report(anomaly, analysis)

    print("\n" + "=" * 70)
    print(f"  INVESTIGATION REPORT — {anomaly.service} — {anomaly.date}")
    print("=" * 70 + "\n")
    print(report)
    print("\n" + "=" * 70)

    missing = [s for s in REQUIRED_SECTIONS if s not in report]
    if missing:
        print(f"\nWARNING: missing sections: {missing}")
    else:
        print(f"\nAll {len(REQUIRED_SECTIONS)} sections present.")
    inference_count = report.count("[INFERENCE]")
    print(f"Inference tags applied: {inference_count}")
