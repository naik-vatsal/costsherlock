# Savings Plans vs Reserved Instances

Both Savings Plans and Reserved Instances reduce AWS compute costs by 30–66% in exchange for a commitment. The key differences are flexibility, coverage scope, and management complexity.

## Side-by-Side Comparison

| Dimension | Reserved Instances | Compute Savings Plans | EC2 Instance Savings Plans |
|-----------|-------------------|----------------------|---------------------------|
| Commitment type | Specific instance type (or family for Convertible) | $/hour spend amount | $/hour for instance family + region |
| Applies to | EC2 only | EC2 + Fargate + Lambda | EC2 only |
| Region flexibility | No (unless Convertible) | Yes — any region | No — locked to one region |
| Instance family flexibility | No (unless Convertible) | Yes | No — locked to one family |
| OS flexibility | No (unless Convertible) | Yes | Yes |
| Max discount | 66% (3-yr Standard RI) | 66% (3-yr Compute SP) | 72% (3-yr EC2 SP) |
| Marketplace | Can sell unused RIs | Cannot sell | Cannot sell |
| Management | Per-instance type inventory | Single $/hour commitment | Single $/hour commitment |

## Discount Examples (m5.xlarge, us-east-1, 1-year)

| Option | Effective Hourly Rate | Monthly Equiv | Savings |
|--------|----------------------|---------------|---------|
| On-Demand | $0.192/hr | $140.16 | — |
| 1yr Standard RI, All Upfront | $0.122/hr | $89.06 | 36% |
| 1yr Compute Savings Plan | $0.131/hr | $95.63 | 32% |
| 1yr EC2 Instance SP | $0.122/hr | $89.06 | 36% |

Savings Plans are slightly less discounted than equivalent RIs but apply automatically to eligible usage.

## When to Choose Savings Plans

Savings Plans are better when:
- You use multiple EC2 instance families and expect to change them over time
- You run workloads on Fargate or Lambda that you want to cover with the same commitment
- You don't want to track which RIs cover which instances (Savings Plans apply automatically)
- Your architecture might change regions in the next year

## When to Choose Reserved Instances

RIs are better when:
- Instance types are stable and won't change for 1–3 years (e.g., RDS, ElastiCache — Savings Plans don't cover these)
- You want the RI Marketplace option (sell unused RIs if you over-bought)
- You're buying Convertible RIs for flexibility within the same family
- You need to cover specific services that Savings Plans don't support (RDS, ElastiCache, Redshift, OpenSearch all require RIs)

## Practical Strategy

Use Savings Plans for EC2, Fargate, and Lambda baseline. Use RIs for RDS, ElastiCache, Redshift, and OpenSearch. Together, this covers all major compute and database services with appropriate discount models for each.

Target: 60–70% Savings Plans coverage for EC2 + Lambda + Fargate, with RI coverage for database services.
