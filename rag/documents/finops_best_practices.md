# FinOps Best Practices for AWS

FinOps (Financial Operations) is the practice of bringing financial accountability to cloud spending. These practices reduce costs and increase visibility without slowing engineering velocity.

## Tagging Strategy

Cost allocation tags are the foundation of FinOps. Without tags, you cannot answer "which team spent what."

Required tags for all resources:
- `Environment`: production | staging | development | sandbox
- `Team`: engineering | data | ml | platform | security
- `Project`: feature name or ticket number
- `Owner`: team email or individual email for personal resources
- `CostCenter`: finance code for chargeback

Enforce via:
- AWS Config rule `required-tags` with auto-remediation (SNS alert)
- Service Control Policies (SCPs) blocking resource creation without mandatory tags
- Terraform `lifecycle { prevent_destroy = true }` for untagged resources

Tagging ROI: A $100,000/month AWS bill with 40% untagged resources = $40,000/month of invisible spend. After tagging, teams self-regulate because they can see their own costs.

## Budget Alerts

AWS Budgets: set thresholds at 50%, 80%, 90%, and 100% of monthly budget:
- Alert at 80% with 10 days remaining in the month = time to investigate
- Alert at 100% forecasted = action required before month end
- Alert at $0 actual + > 200% of expected = anomaly detection

Budget cost: $0.062/budget-day for 62 budgets = $3.84/month for comprehensive coverage.

## Regular Review Cadence

**Weekly (15 minutes):** Review Cost Explorer for anomalies vs prior week. Check Trusted Advisor cost recommendations.

**Monthly (2 hours):** Review RI coverage and utilization. Rightsize recommendations. Review idle resources (stopped EC2, orphaned EBS, unattached EIPs).

**Quarterly (4 hours):** Evaluate Savings Plans commitments. Review Reserved Instance renewals. Check for new pricing models or service alternatives.

## Rightsizing

AWS Compute Optimizer provides free rightsizing recommendations:
- EC2: over-provisioned instances with CPU < 10% for 14 days
- Lambda: functions where memory is >50% unused
- EBS: over-provisioned volume types

Typical rightsizing savings: 20–40% of compute costs.
- 100 × m5.xlarge all over-provisioned: $14,016/month
- After rightsizing to m5.large: $7,008/month
- **Annual savings: $84,096**

## Chargeback vs Showback

**Showback**: Show teams their AWS costs without billing them back. Encourages awareness.
**Chargeback**: Bill teams internally for their cloud usage. Creates direct financial accountability.

Chargeback requires accurate tagging. Start with showback and move to chargeback once tagging reaches >90% coverage.
