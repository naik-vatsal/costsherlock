# EC2 Reserved Instances vs On-Demand

Reserved Instances (RIs) offer significant discounts in exchange for a 1-year or 3-year usage commitment. They do not reserve capacity by default — they are a billing discount applied to matching on-demand usage.

## Discount Tiers (m5.xlarge, us-east-1, Linux)

| Payment Option       | 1-Year Cost  | Monthly Equiv | Savings vs On-Demand |
|----------------------|-------------|---------------|----------------------|
| On-Demand            | $1,681/yr   | $140.16/mo    | —                    |
| 1yr No Upfront       | $1,138/yr   | $94.84/mo     | 32%                  |
| 1yr Partial Upfront  | $1,094/yr   | $91.17/mo     | 35%                  |
| 1yr All Upfront      | $1,072/yr   | $89.33/mo     | 36%                  |
| 3yr No Upfront       | $2,124/3yr  | $59.00/mo     | 58%                  |
| 3yr All Upfront      | $1,893/3yr  | $52.58/mo     | 62%                  |

## What Happens When an RI Expires

This is a critical cost trap. When a Reserved Instance term ends, the instance **immediately reverts to on-demand pricing** with no warning by default. An m5.xlarge running continuously will jump from $89/month back to $140/month overnight — a 57% cost increase. AWS sends no automatic notification unless you configure a Cost Anomaly Detection monitor or a Billing Alert.

In practice, a fleet of 20 × m5.xlarge RIs expiring simultaneously costs an extra $1,017/month ($12,204/year) if not renewed.

## Convertible RIs
Convertible RIs allow instance family, OS, and tenancy changes during the term. They offer slightly lower savings (31% vs 36% for 1yr all-upfront) but provide flexibility when your workload may change.

## Standard RIs
Standard RIs cannot be modified but can be sold on the AWS Reserved Instance Marketplace. They offer the highest discount but are fully committed.

## RI Monitoring Best Practice
- Set a CloudWatch billing alarm at 110% of current monthly spend
- Use AWS Budgets to alert 60 days before RI expiry
- Review Cost Explorer RI utilization report monthly — idle RIs still consume commitment
- An RI with 0% utilization for 30 days represents pure wasted spend equal to the monthly amortized cost
