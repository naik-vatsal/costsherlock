# Cost Trap: S3 Versioning Without Lifecycle Cleanup

S3 versioning protects against accidental deletion and overwrites by retaining all previous versions of every object. Without a lifecycle policy to expire old versions, every write operation doubles (or more) the stored data permanently.

## How Versioning Multiplies Storage

With versioning enabled, each PUT operation creates a new version. The previous version is retained. With no cleanup policy:
- Write #1: 1 version stored
- Write #2: 2 versions stored (1 current + 1 noncurrent)
- Write #10: 10 versions stored
- After 1 year of daily writes to 10,000 files: 3.65 million versions stored

## Cost Example: Database Backup Bucket

A team stores daily RDS snapshots as 50 GB files in a versioned S3 bucket:

| Month | Files Written | Versions Stored | Storage Cost |
|-------|--------------|-----------------|-------------|
| 1     | 30           | 30 versions × 50 GB = 1,500 GB | $34.50 |
| 3     | 90           | 90 versions = 4,500 GB | $103.50 |
| 6     | 180          | 180 versions = 9,000 GB | $207.00 |
| 12    | 365          | 365 versions = 18,250 GB | **$419.75** |

If the team only needs 30 days of backups, 335 versions at 50 GB each = 16,750 GB of unnecessarily stored data = $385.25/month wasted.

## Delete Markers Add Cost Too

When an object is deleted in a versioned bucket, S3 inserts a "delete marker" instead of removing the data. The previous version still exists and is still billed. Only explicitly deleting specific version IDs removes data.

An application that creates and deletes many temporary files:
- 1 million creates + 1 million deletes = 1 million delete markers + 1 million old versions
- All retained indefinitely, all billed at $0.023/GB

## The Fix: Noncurrent Version Expiration

Add a lifecycle rule to expire noncurrent versions:
```json
{
  "Filter": {},
  "NoncurrentVersionExpiration": { "NoncurrentDays": 30 },
  "ExpiredObjectDeleteMarker": true
}
```

This keeps the current version and 30 days of history. The cost difference for the backup example above: $419.75/month vs ~$34.50/month. **Annual saving: $4,623.**

## Detection

CloudTrail: `PutBucketVersioning` with `Status: Enabled` marks when versioning was turned on. If no corresponding lifecycle rule exists for noncurrent version expiration, this bucket is accumulating old versions.
