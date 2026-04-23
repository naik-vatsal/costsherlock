# AWS Pricing Models: On-Demand, Reserved, Savings Plans, and Spot

AWS offers four main pricing models for compute. Choosing the right model for each workload type is one of the highest-leverage cost optimization decisions available.

## On-Demand

Pay per second (or hour for some services) with no commitment. The most flexible and the most expensive.

Use when:
- Workload duration is unpredictable or short-term
- New application where usage patterns are unknown
- Burst capacity beyond your reserved baseline

Example: m5.xlarge on-demand = $0.192/hr ($140.16/month)

## Reserved Instances

1-year or 3-year commitment in exchange for 32–66% discount. Comes in Standard (fixed) and Convertible (modifiable) forms.

| Payment | 1-Year Discount | 3-Year Discount |
|---------|----------------|----------------|
| No Upfront | 32% | 48% |
| Partial Upfront | 35% | 54% |
| All Upfront | 36% | 62% |

Use when:
- Workload runs at least 70% of the time for 1+ years
- Instance family and region are known and stable
- Can commit to 1 or 3 years

Example: m5.xlarge 1-yr All Upfront = $89.33/month equivalent (36% savings)

## Savings Plans

More flexible than RIs — applies to any EC2 instance in any region and any size, or any Lambda compute. Two types:

**Compute Savings Plans** (most flexible, 66% max discount):
- Applies to EC2 regardless of family, size, region, OS, or tenancy
- Applies to Fargate and Lambda

**EC2 Instance Savings Plans** (66% max discount for specific instance family in a region):
- Must commit to instance family + region (e.g., M5 in us-east-1)
- Higher discount than Compute plans for same family

Pricing: you commit to a $/hour spend (e.g., $5/hr), any EC2/Lambda/Fargate usage up to that amount is covered at the savings plan rate. Overages are charged at on-demand.

## Spot Instances

Spare capacity at 60–90% discount with 2-minute interruption warning.

Use when:
- Fault-tolerant workloads (batch, CI/CD, ML training)
- Stateless services with checkpointing
- Flexible start/end time

Savings: c5.2xlarge spot ~$0.085/hr vs $0.340/hr on-demand (75% savings)

## Decision Framework

| Workload Characteristic | Best Model |
|------------------------|-----------|
| 24/7 production, 1+ year | Reserved or Savings Plans |
| Variable, AWS-family flexible | Compute Savings Plans |
| Fault-tolerant batch | Spot |
| Short-lived test or new project | On-Demand |
| Mix of steady + burst | Reserved baseline + On-Demand burst |
