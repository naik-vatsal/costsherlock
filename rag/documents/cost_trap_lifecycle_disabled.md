# Cost Trap: S3 Lifecycle Policy Disabled or Deleted

Disabling or removing an S3 lifecycle policy causes objects to accumulate in S3 Standard storage indefinitely. This trap is insidious because costs grow silently over weeks and months before becoming visible in billing.

## What Happens When Lifecycle Is Removed

Before policy removal: objects transition as configured — e.g., to Standard-IA after 30 days, Glacier after 90 days. After a `DeleteBucketLifecycle` or `PutBucketLifecycleConfiguration` with empty rules:
- All new objects stay in Standard forever at $0.023/GB-month
- Existing objects already in Glacier or Standard-IA are unaffected
- Old versions in versioned buckets are never cleaned up
- Incomplete multipart uploads are never aborted

## Quantified Impact

**Scenario: Application log bucket, 100 GB/day ingestion**

With working lifecycle policy (transition to Glacier after 90 days):
- Days 0–30: ~3,000 GB in Standard = $69/month
- Days 31–90: transitions to Standard-IA = $37.50/month
- Days 91+: transitions to Glacier Flexible = $10.80/month
- Steady-state blended cost: ~$40/month

After lifecycle policy deleted (day 91 onward, all in Standard):
- Month 1 post-deletion: 3,000 GB accumulating + 3,000 GB already transitioning
- Month 3 post-deletion: 9,000 GB in Standard = $207/month
- Month 6 post-deletion: 18,000 GB in Standard = $414/month

**Monthly cost increase from deleted lifecycle: $374/month after 6 months.**

## Detection

CloudTrail event: `DeleteBucketLifecycle` or `PutBucketLifecycleConfiguration` with `requestParameters.LifecycleConfiguration = {}`.

Cost Explorer: S3 Standard storage bytes growing faster than data ingestion rate suggests lifecycle stopped working. Standard storage should plateau or grow slowly if lifecycle is active.

## Common Cause

Lifecycle policies are sometimes inadvertently removed during:
- Terraform `terraform destroy` + `terraform apply` with lifecycle rules missing from new config
- Console-based policy edits that clear all rules
- Cross-account bucket replication setup that resets bucket configuration

## Remediation
1. Restore lifecycle policy from IaC source of truth or backup
2. Retroactively transition objects with S3 Batch Operations (cost: $0.25 per 1M objects processed)
3. Add CloudWatch Event rule alerting on `DeleteBucketLifecycle` CloudTrail events
