# RDS Storage Pricing

RDS storage is billed per GB-month separately from instance hours. Storage costs continue even when an instance is stopped (though instance-hour billing pauses for up to 7 days).

## Storage Types and Prices (us-east-1)

| Storage Type | Price/GB-month | Notes                                  |
|--------------|----------------|----------------------------------------|
| gp2 (SSD)    | $0.115/GB      | Baseline 3 IOPS/GB, burst to 3,000    |
| gp3 (SSD)    | $0.115/GB      | 3,000 IOPS included, better baseline  |
| io1 (SSD)    | $0.125/GB      | Plus $0.10/IOPS provisioned            |
| Magnetic      | $0.10/GB       | Legacy, not recommended                |

## IOPS Pricing for io1
io1 charges separately for provisioned IOPS:
- Storage: $0.125/GB-month
- IOPS: $0.10 per provisioned IOPS-month

A 1 TB io1 volume with 5,000 IOPS:
- Storage: 1,000 GB × $0.125 = $125/month
- IOPS: 5,000 × $0.10 = $500/month
- **Total: $625/month** for storage alone

The same workload on gp3 with 5,000 IOPS:
- Storage: 1,000 GB × $0.115 = $115/month
- Extra IOPS above 3,000: 2,000 × $0.02 = $40/month
- **Total: $155/month** — 75% cheaper than io1 for this use case

## Autoscaling Storage Growth
RDS storage autoscaling can expand storage up to a configured maximum. Storage **never shrinks** automatically. A database that grows from 500 GB to 2 TB over 6 months will cost $230/month in storage after expansion, and the storage charge persists even if 1.5 TB of old data is deleted (free space, but still allocated and billed).

## RDS Automated Backups
Backup storage equal to your database storage is provided free. Storage beyond 100% of database size is charged at $0.095/GB-month. A 500 GB database with 14-day retention accumulates up to ~7 TB of backup data — the 6.5 TB above 500 GB costs $617.50/month in backup storage.

## Multi-AZ Storage Cost
Multi-AZ doubles storage cost because both instances maintain full copies. A Multi-AZ db.r5.2xlarge with 2 TB storage:
- Instance (Multi-AZ): $0.960 × 2 = $1.92/hr ($1,401.60/month)
- Storage (gp2): 2,000 × $0.115 × 2 = $460/month
- **Total storage + instance: ~$1,862/month**
