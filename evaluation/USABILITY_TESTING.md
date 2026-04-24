# CostSherlock Usability Testing — Time-to-Insight Protocol

**Metric:** Time to Insight (Metric 6 of 7)  
**Owner:** Priti Ghosh  
**Target:** < 3 minutes (180 seconds) for a non-engineer to identify the root cause of the highest-severity anomaly

---

## Objective

Measure how quickly a user unfamiliar with the system can navigate the CostSherlock
dashboard and verbally identify the root cause of the most severe AWS cost anomaly
without any coaching beyond the initial task description.

---

## Participants

- **Target:** 5 minimum participants per evaluation round
- **Profile:** Non-engineers (finance analysts, product managers, business stakeholders)
  with basic familiarity with AWS billing concepts but no CloudTrail or cost investigation experience
- **Recruitment:** Internal stakeholders or students from adjacent programs

---

## Setup

1. Launch a fresh CostSherlock session with the synthetic demo data pre-loaded:
   ```bash
   python demo.py          # pre-run pipeline so reports are cached
   streamlit run dashboard/app.py
   ```
2. Navigate to the **Timeline** view before handing off to the participant.
3. Do NOT pre-select any anomaly or open any investigation.
4. Provide the participant with the task prompt below — nothing else.

---

## Task Prompt (read verbatim to participant)

> "You are a cloud finance analyst. Your engineering team's AWS bill spiked
> unexpectedly last month. Using this dashboard, find the most severe cost
> anomaly and tell me what caused it. Start whenever you're ready."

Start the timer when the participant says "ready" or begins interacting with the dashboard.

---

## Measurement

| Milestone | What to record |
|-----------|---------------|
| **T₀** | Participant begins interacting with the dashboard |
| **T₁** | Participant opens the Investigation view for the highest-severity anomaly |
| **T₂** | Participant verbally states the root cause (any correct restatement of the Executive Summary counts) |
| **T_total** | T₂ − T₀ |

Record T_total in seconds. Also note whether the participant:
- Found the correct anomaly (highest z-score)
- Stated the correct service (EC2 / S3 / CloudWatch)
- Stated the correct causal mechanism (not just "costs went up")

---

## Success Criteria

| Threshold | Rating |
|-----------|--------|
| T_total ≤ 60 s | Excellent |
| T_total ≤ 120 s | Good |
| T_total ≤ 180 s | Meets target |
| T_total > 180 s | Below target — investigate UX friction points |

**Pass condition:** Median T_total across all 5+ participants ≤ 180 seconds.

---

## Data Collection Sheet

```
Participant ID : ___________
Date           : ___________
T₀ (start)     : ___________
T₁ (opened)    : ___________
T₂ (answered)  : ___________
T_total (s)    : ___________
Correct anomaly? (Y/N) : ___
Correct service?  (Y/N): ___
Correct mechanism?(Y/N): ___
Notes          : ___________
```

---

## Aggregate Reporting

After all sessions, compute:
- Median T_total
- Mean T_total
- % participants who identified the correct root cause
- % participants who completed within 180 s

Report median as the headline metric (robust to outliers).

---

## UX Friction Log

During each session, note any moment where the participant hesitates for > 10 seconds
or asks a question. These are friction points. Common categories:

- **Navigation confusion** — cannot find the right view
- **Terminology** — unfamiliar with z-score, CloudTrail, delta
- **Information overload** — too many hypothesis details before the summary
- **Trust barrier** — participant questions whether the report is accurate

---

*Priti Ghosh — Northeastern University — INFO 7375 Generative AI*
