# Cost Trap: Accumulating EBS Snapshots

EBS snapshots are stored incrementally in S3, but the billing model causes costs to grow over time in ways that surprise many teams. Old snapshots from deleted instances can persist and accumulate charges indefinitely.

## EBS Snapshot Pricing
- $0.05/GB-month for all snapshot storage (us-east-1)
- Charged on total unique snapshot data, not individual snapshot size

## How Incremental Snapshots Compound

Incremental snapshots only store changes since the last snapshot — but you must keep the full chain to restore any snapshot. If you take daily snapshots of a 500 GB volume with 5% daily change rate:

| Age   | Snapshot | Data Added | Cumulative Billed | Monthly Cost |
|-------|----------|------------|-------------------|-------------|
| Day 1 | snap-001 | 500 GB     | 500 GB            | $25.00      |
| Day 2 | snap-002 | 25 GB      | 525 GB            | $26.25      |
| Day 7 | snap-007 | 25 GB each | 650 GB            | $32.50      |
| Day 30| snap-030 | 25 GB each | 1,225 GB          | $61.25      |
| Day 90| snap-090 | 25 GB each | 3,225 GB          | $161.25     |

Without a snapshot lifecycle policy, snapshot costs grow without bound.

## The Orphaned Snapshot Problem

When an EC2 instance or AMI is deleted, its snapshots are **not automatically deleted**. Snapshots backing registered AMIs cannot be deleted without deregistering the AMI first.

A team decommissioning old AMI versions every month over a year:
- 12 AMIs × ~20 snapshots per AMI (one per volume/region)
- 240 orphaned snapshots × 100 GB average = 24,000 GB
- Cost: 24,000 GB × $0.05 = **$1,200/month** in orphaned snapshot storage

## Snapshot Lifecycle Policies (DLM)
AWS Data Lifecycle Manager (DLM) is free and automates snapshot creation and deletion:
- Create daily snapshots with 7-day retention
- Cost capped at 7 × (daily_change_rate) GB rather than growing indefinitely
- For a 500 GB volume with 5% change: ~575 GB of snapshot storage = $28.75/month forever

## Detection
Cost Explorer: filter by "EC2: EBS Snapshot" usage type. A rising line with no corresponding increase in running instances indicates accumulating orphaned snapshots.

AWS CLI to list snapshots not associated with any running volume or AMI:
```bash
aws ec2 describe-snapshots --owner-ids self \
  --query 'Snapshots[?not_null(Description) == `false`]'
```
