# Cost Trap: Idle Load Balancers

Application Load Balancers (ALB) and Network Load Balancers (NLB) charge a minimum hourly rate regardless of traffic. An unused load balancer provisioned for a test environment or decommissioned service continues billing until explicitly deleted.

## Load Balancer Pricing

| Type | Hourly Charge | LCU/NLCU Charge           |
|------|--------------|---------------------------|
| ALB  | $0.008/hr    | $0.008/LCU-hour           |
| NLB  | $0.008/hr    | $0.006/NLCU-hour          |
| CLB (Classic) | $0.025/hr | $0.008 per GB processed |

**Minimum monthly cost (zero traffic):**
- ALB: $0.008 × 24 × 30 = **$5.76/month**
- NLB: $0.008 × 24 × 30 = **$5.76/month**
- CLB: $0.025 × 24 × 30 = **$18.00/month**

## Load Balancer Capacity Units (LCUs)

ALB LCU pricing is based on the highest of:
- New connections: 25 per second = 1 LCU
- Active connections: 3,000 per minute = 1 LCU
- Processed bytes: 1 GB per hour = 1 LCU
- Rule evaluations: 1,000 per second = 1 LCU

A typical production ALB handling 1,000 requests/second at 10 KB average:
- Processed bytes: 1,000 × 10 KB = 10 MB/s = 36 GB/hr = 36 LCUs
- LCU cost: 36 × $0.008 = $0.288/hr ($210.24/month)
- Hourly charge: $5.76/month
- **Total ALB cost: $216/month for that traffic level**

## The Accumulation Pattern

In a typical enterprise with 5 environments (dev, staging, QA, UAT, prod), each running separate ALBs:
- 5 ALBs × $5.76 baseline = $28.80/month in idle charges
- If ALBs remain after project shutdown: $28.80/month forever
- 10 forgotten ALBs from old projects: $57.60/month = $691.20/year

Over a 3-year period, 20 forgotten ALBs from ended projects: $4,147.20 in pure waste.

## Detection

In Cost Explorer, filter "Service: EC2" + "Usage Type: LoadBalancerUsage". LBs with zero RequestCount CloudWatch metric but non-zero billing are idle candidates.

CLI check for low-traffic load balancers:
```bash
aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB \
  --metric-name RequestCount --dimensions Name=LoadBalancer,Value=<arn> \
  --start-time 2024-01-01 --end-time 2024-01-31 --period 2592000 --statistics Sum
```

## Remediation
Delete load balancers with zero RequestCount for 30+ days. If uncertain, set to 0 desired targets (keeping the LB) and verify no traffic before deletion.
