# S3 Lifecycle Policies

S3 Lifecycle policies automate transitioning objects between storage classes and expiring old versions. When lifecycle policies are missing or disabled, objects accumulate in Standard storage indefinitely.

## How Lifecycle Policies Work
A lifecycle rule targets a bucket, prefix, or tag. Rules can:
1. **Transition** objects to a cheaper class after N days
2. **Expire** (delete) objects after N days
3. **Delete noncurrent versions** in versioned buckets
4. **Abort incomplete multipart uploads** after N days

## Example Lifecycle Configuration (Cost Optimized)
```
Day 0–30:   S3 Standard ($0.023/GB)
Day 30–90:  S3 Standard-IA ($0.0125/GB) — transition after 30 days
Day 90–365: S3 Glacier Flexible ($0.0036/GB) — transition after 90 days
Day 365+:   Delete (or move to Deep Archive at $0.00099/GB)
```

For 1 TB of logs following this policy vs storing in Standard forever:
- Standard forever: $0.023 × 1,000 GB × 12 months = $276/year
- With lifecycle: ~$47/year in blended storage costs
- Annual saving: $229 per TB of log data

## What Breaks When Lifecycle is Disabled

A `PutBucketLifecycleConfiguration` CloudTrail event that **removes** rules is the most dangerous operation. Within 30 days of a lifecycle policy being deleted:
- Objects stop transitioning to Standard-IA or Glacier
- All new objects land and stay in Standard
- Existing objects in cheaper classes are unaffected (already transitioned)
- Versioned buckets accumulate old versions at $0.023/GB with no cleanup

For a bucket ingesting 500 GB/day of application logs with no lifecycle policy:
- Day 30: 15 TB stuck in Standard = $345/month growing
- Day 90: 45 TB in Standard = $1,035/month

## Incomplete Multipart Uploads
Incomplete multipart uploads are invisible in the console but accumulate storage charges at Standard rates. A lifecycle rule with `AbortIncompleteMultipartUpload: Days: 7` is free and prevents this. A busy media upload service can accumulate hundreds of GB in incomplete parts over months.

## CloudTrail Correlation
When investigating an S3 cost spike, check CloudTrail for `PutBucketLifecycleConfiguration` and `DeleteBucketLifecycle` events in the 14 days preceding the anomaly.
