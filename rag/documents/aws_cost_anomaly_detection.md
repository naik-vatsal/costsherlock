# AWS Cost Anomaly Detection: Native Capabilities and Limitations

AWS provides a native Cost Anomaly Detection service that uses machine learning to identify unexpected spending. Understanding its capabilities — and where it falls short — clarifies the value that CostSherlock adds.

## What AWS Cost Anomaly Detection Does

AWS Cost Anomaly Detection monitors spending by service, linked account, member account, or cost category. It uses ML models trained on your historical spend to identify anomalies.

**Setup cost:** Free to enable. Alerts via SNS or email.
**Alert threshold:** Configurable — e.g., alert when anomaly > $100 absolute or > 20% relative.

When an anomaly is detected, AWS provides:
- Which service or account is anomalous
- The expected vs actual spend
- Start and end time of the anomaly
- A dollar impact estimate

## AWS Cost Anomaly Detection Pricing
- Anomaly detection itself: Free
- SNS notifications: $0.50 per 1M notifications
- Email alerts: Free
- API calls to retrieve anomalies: Free (normal API pricing)

## Limitations of Native AWS Detection

**1. No root cause identification**
AWS tells you *that* EC2 costs spiked by $5,000. It does not tell you *why* — which instances, which ASG, which CloudTrail event caused it.

**2. No CloudTrail correlation**
The native service does not cross-reference cost changes with infrastructure modifications. Linking a `ModifyDBInstance` event at 2pm to an RDS cost spike starting at 2pm requires manual investigation.

**3. No causal chain reasoning**
AWS identifies the anomaly but cannot explain the chain: "Developer enabled Multi-AZ → RDS cost doubled → anomaly."

**4. Service-level granularity only**
Anomaly monitors at the service or account level. Within EC2, it cannot distinguish which instance type, which ASG, or which region drove the spike without manual filtering in Cost Explorer.

**5. No remediation suggestions**
The native service identifies and quantifies anomalies but does not suggest fixes or estimate savings from corrective actions.

## Where CostSherlock Adds Value

CostSherlock addresses each limitation:
- **Sentinel agent**: z-score detection at service-level granularity (matches AWS capability)
- **Detective agent**: CloudTrail correlation to identify the triggering event
- **Analyst agent**: RAG-based reasoning to explain the causal mechanism with cited evidence
- **Narrator agent**: Generates remediation steps with estimated cost savings

The combination transforms "EC2 costs spiked $5,000" into "A `CreateAutoScalingGroup` event at 14:32 UTC by role `terraform-prod` launched 20 × m5.xlarge instances unexpectedly. Expected cost impact: +$2,995/month. Recommended fix: audit ASG max capacity; current max=100 should be 20."
