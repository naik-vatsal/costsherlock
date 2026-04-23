# EBS Volume Pricing

Elastic Block Store (EBS) volumes are charged per GB-month provisioned, not per GB used. A 1 TB volume that is 10% full costs the same as a 1 TB volume that is 100% full.

## Volume Type Prices (us-east-1)

| Type   | Description          | Storage Price   | IOPS / Throughput Add-On                      |
|--------|----------------------|-----------------|------------------------------------------------|
| gp2    | General SSD          | $0.10/GB-month  | 3 IOPS/GB free, burst to 3,000 IOPS            |
| gp3    | Latest gen SSD       | $0.08/GB-month  | 3,000 IOPS + 125 MB/s included free            |
| io1    | Provisioned IOPS SSD | $0.125/GB-month | $0.065 per provisioned IOPS-month              |
| io2    | Higher durability    | $0.125/GB-month | $0.065/IOPS (first 32K), $0.046/IOPS (32K+)   |
| st1    | Throughput HDD       | $0.045/GB-month | Max 500 MB/s, not for boot volumes              |
| sc1    | Cold HDD             | $0.015/GB-month | Max 250 MB/s, cheapest block storage           |

## gp2 vs gp3 Cost Comparison
For a 500 GB general-purpose volume:
- gp2: 500 × $0.10 = $50/month
- gp3: 500 × $0.08 = $40/month
- Savings: $10/month ($120/year) per volume — just by migrating to gp3 with no performance loss

For 100 volumes across a fleet: $1,200/year in savings from a zero-risk volume type change.

## io1 at Scale Is Expensive
A database volume: 2 TB io1 with 20,000 provisioned IOPS:
- Storage: 2,000 GB × $0.125 = $250/month
- IOPS: 20,000 × $0.065 = $1,300/month
- **Total: $1,550/month**

Equivalent on io2: $250 + (20,000 × $0.065) = $1,550/month for up to 32K IOPS, but io2 offers 10× better durability (99.999% vs 99.8% SLA).

## EBS Snapshot Pricing
- EBS snapshots: $0.05/GB-month (stored in S3, incremental)
- A 1 TB volume with daily snapshots, 10% daily change rate:
  - Initial snapshot: 1,000 GB × $0.05 = $50
  - Each subsequent daily snapshot: ~100 GB × $0.05 = $5
  - After 30 days: $50 + (29 × $5) = **$195/month in snapshots**

## Orphaned Volumes
When an EC2 instance is terminated, attached EBS volumes are **not automatically deleted** unless the `DeleteOnTermination` flag was set. A terminated instance leaves behind volumes still billed at full storage price. A forgotten 500 GB gp3 volume: $40/month indefinitely.
