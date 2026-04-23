# Cost Trap: Unused and Orphaned EBS Volumes

When an EC2 instance is terminated, its attached EBS volumes are **not automatically deleted** unless the `DeleteOnTermination` attribute was set to `true` at launch. Orphaned volumes continue billing at full price indefinitely — no alerts, no warnings.

## How the Trap Works

Default behavior in EC2: the root volume has `DeleteOnTermination: true`, but additional data volumes default to `DeleteOnTermination: false`. In practice, many instances are launched without explicitly setting this flag, leaving data volumes alive after termination.

A common scenario:
1. Developer launches m5.2xlarge with 3 attached EBS volumes (500 GB total)
2. Instance is terminated after testing
3. Root volume deleted (default), but 2 data volumes (400 GB total) remain
4. Monthly cost: 400 GB × $0.10/GB = **$40/month per forgotten instance set**
5. After 6 months of accumulated orphaned volumes: potentially hundreds of idle volumes

## Real Cost Accumulation Example

Team of 10 developers, each creating 2 test instances per week, each with 200 GB of attached storage:
- Instances properly terminated, volumes left behind
- Weekly orphaned storage: 10 × 2 × 200 GB = 4,000 GB new orphaned storage
- Monthly accumulation: ~16,000 GB at $0.10/GB = **$1,600/month** after one month
- After 3 months: $4,800/month in idle EBS storage

## Identifying Orphaned Volumes

In Cost Explorer, filter by "Service: EC2" and "Usage Type: EBS:VolumeUsage.gp2" (or gp3). A growing cost with flat EC2 instance count indicates orphaned volumes.

CLI check:
```bash
aws ec2 describe-volumes --filters Name=status,Values=available \
  --query 'Volumes[*].{ID:VolumeId,Size:Size,Created:CreateTime}'
```
Volumes in `available` state (not attached to any instance) are the orphans.

## Remediation
1. Set `DeleteOnTermination: true` for all volumes in launch templates
2. Run monthly automated report of `available` volumes older than 7 days
3. Tag volumes with instance ID and owner at creation for attribution
4. AWS Config rule `ec2-volume-inuse-check` alerts on unattached volumes
5. Delete confirmed orphans: $0.08–$0.125/GB-month savings per GB removed
