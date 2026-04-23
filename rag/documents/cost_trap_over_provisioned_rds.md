# Cost Trap: Over-Provisioned RDS Instances

RDS instances are frequently over-provisioned — chosen for peak load or "just in case" capacity that never materializes. Because RDS pricing is linear with instance size, an oversized instance is a constant monthly tax with no operational benefit.

## The Cost Gap Between Instance Tiers

| Appropriate Size   | Actual Used  | Monthly Cost | Wasted Monthly |
|-------------------|-------------|-------------|----------------|
| db.t3.medium ($50)| db.r5.large ($175) | $175 | $125 |
| db.m5.large ($125)| db.r5.2xlarge ($700) | $700 | $575 |
| db.t3.large ($100)| db.r5.4xlarge ($1,400) | $1,400 | $1,300 |

## Real-World Pattern: "We Might Need It" Sizing

A startup launches with a db.r5.4xlarge ($1,401.60/month) "to handle expected growth." After 12 months, CloudWatch shows:
- Average CPU: 4% (threshold for downsizing: >60%)
- Average free memory: 110 GB of 128 GB (>85% idle)
- Average read IOPS: 150 (vs 18,750 max)
- Average write IOPS: 50 (vs 18,750 max)

The workload actually fits on a db.t3.large ($99.28/month):
- Monthly waste: $1,401.60 - $99.28 = **$1,302.32/month**
- Annual waste: **$15,627.84**

## db.r5 vs db.t3 Decision Matrix

Use db.t3 (burstable) when:
- Average CPU is below 20%
- Workload is not sustained (business hours only)
- Cost priority > consistent performance

Use db.r5 (memory optimized) when:
- Large working sets that must fit in RAM (e.g., full dataset in buffer pool)
- Sustained high CPU workloads
- Low-latency requirements that can't tolerate CPU credit exhaustion

## RDS CloudWatch Metrics for Right-Sizing

Key metrics to evaluate (via CloudWatch, 14-day average):
- `CPUUtilization`: if < 10%, severely over-provisioned
- `FreeableMemory`: if > 50% of total RAM, could downsize
- `ReadIOPS` + `WriteIOPS`: compare to instance IOPS limit
- `DatabaseConnections`: if < 20% of max_connections, smaller instance works

## Changing RDS Instance Class

`ModifyDBInstance --db-instance-class` causes a few minutes of downtime (or during next maintenance window). A `ModifyDBInstance` event in CloudTrail with a larger instance class (e.g., changing from db.t3.medium to db.r5.4xlarge) is a strong cost anomaly signal.
