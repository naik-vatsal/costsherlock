# Troubleshooting S3 Cost Spikes

S3 cost spikes typically fall into four categories: unexpected storage growth, request volume increase, data transfer charges, or a configuration change that disabled cost controls.

## Step 1: Categorize the Increase
In Cost Explorer, filter by S3 and group by Usage Type:
- `TimedStorage-ByteHrs` — storage costs, measured in GB-hours
- `Requests-Tier1` (PUT/POST) and `Requests-Tier2` (GET) — request costs
- `DataTransfer-Out-Bytes` — egress to internet
- `S3-Egress-Bytes` — data leaving S3 to other services

Identify which category drove the spike before investigating root causes.

## Step 2: Lifecycle Policy Disabled or Deleted

**Check:** S3 console → bucket → Management → Lifecycle rules
**CloudTrail signal:** `DeleteBucketLifecycle` or `PutBucketLifecycleConfiguration` with empty rules
**Cost impact:** Objects stop transitioning; 100 GB/day bucket grows at $0.023/GB without limits

Action: Restore lifecycle rules from IaC immediately.

## Step 3: Versioning Without Noncurrent Expiration

**Check:** S3 → bucket → Properties → Bucket Versioning = Enabled
**Follow-up:** Check for lifecycle rule with `NoncurrentVersionExpiration`
**Cost impact:** Every write creates a new version; high-churn buckets can double/triple storage
**CloudTrail signal:** `PutBucketVersioning` with no corresponding lifecycle update

## Step 4: Transfer Acceleration Enabled

**Check:** S3 → bucket → Properties → Transfer Acceleration = Enabled
**CloudTrail signal:** `PutBucketAccelerateConfiguration` with Status=Enabled
**Cost impact:** +$0.04–$0.08/GB on all uploads; 10 TB/month = $400–$800 extra

## Step 5: Request Volume Spike

**Check:** CloudWatch → S3 → AllRequests metric per bucket
**Signal:** AllRequests 10× above baseline
**Root causes:**
- Application bug causing infinite retry loop on S3 GET/PUT
- Broken pagination causing LIST request storm ($0.005 per 1,000 LISTs)
- Web crawler indexing public bucket

A bug causing 100M extra PUT requests: 100M / 1,000 × $0.005 = $500.

## Step 6: Cross-Region Replication Activated

**Check:** S3 → bucket → Management → Replication rules
**CloudTrail signal:** `PutBucketReplication`
**Cost impact:** $0.02/GB transfer + destination storage cost

## Step 7: Public Bucket Bandwidth Abuse

**Check:** S3 server access logs or CloudFront distribution logs for anomalous GET patterns
**Signal:** Sudden spike in `DataTransfer-Out` from a specific bucket
**Cost impact:** $0.09/GB to internet

Action: Enable S3 Block Public Access or move content behind CloudFront with origin access control.
