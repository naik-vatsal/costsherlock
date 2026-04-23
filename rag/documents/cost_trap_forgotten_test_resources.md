# Cost Trap: Forgotten Dev and Staging Resources

Development and testing resources left running after business hours, over weekends, or after a project ends are one of the largest controllable AWS cost categories. Unlike production workloads, dev/staging resources have zero revenue justification when idle.

## Typical Forgotten Resource Costs

**Dev environment left running over a 3-day weekend:**
- 3 × m5.xlarge EC2: 3 × $0.192 × 72 hrs = $41.47
- 1 × db.t3.large RDS: $0.136 × 72 hrs = $9.79
- 1 × ElastiCache cache.r6g.large: $0.154 × 72 hrs = $11.09
- **Weekend cost: $62.35** for one team's dev environment

For 10 teams: $623.50 per 3-day weekend = $5,611.50/year just from long weekends.

**Staging environment for a completed project:**
Running for 6 months after the project was decommissioned:
- 5 × m5.2xlarge: 5 × $0.384 = $1.92/hr ($1,382.40/month)
- 2 × db.r5.xlarge Multi-AZ: 2 × $0.960 = $1.92/hr ($1,382.40/month)
- 2 × NAT Gateways: $64.80/month
- EBS and other: ~$200/month
- **Monthly waste: ~$3,029** ($18,174 over 6 months)

## The Tag-Based Detection Strategy

Resources without cost allocation tags are the most likely to be forgotten. A simple tagging policy requiring:
- `Environment`: dev | staging | prod
- `Owner`: team or person email
- `Project`: project name
- `Shutdown`: date after which resource should be reviewed

AWS Config rule `required-tags` flags any resource missing mandatory tags. Non-tagged resources are the first to investigate when looking for forgotten tests.

## Scheduled Shutdowns with Instance Scheduler

AWS Instance Scheduler (open-source) or Systems Manager Automation:
- Stop dev EC2 instances at 7pm, restart at 8am weekdays
- Stop RDS at 8pm (RDS can be stopped for up to 7 days)
- Savings: 73 off-hours per week = 73/168 = 43% reduction in instance hours

For the 3 × m5.xlarge dev fleet above:
- Always-on: 3 × $0.192 × 730 = $420.48/month
- Scheduled (8am–7pm weekdays only): ~$155/month
- **Monthly savings: $265.48**

## CloudTrail Correlation

`RunInstances` events that launch instances without mandatory tags, or resource creations tagged with `Environment: dev` more than 30 days old in Cost Explorer, are the strongest signals.
