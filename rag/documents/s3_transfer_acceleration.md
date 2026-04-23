# S3 Transfer Acceleration Pricing

S3 Transfer Acceleration routes uploads through AWS CloudFront edge locations, improving upload speed for users far from the S3 bucket's home region. It applies only to data flowing **into** S3 (uploads), not downloads.

## Pricing

| Transfer Direction                        | Additional Charge         |
|-------------------------------------------|---------------------------|
| Upload to S3 via edge, same continent     | +$0.04/GB                 |
| Upload to S3 via edge, different continent| +$0.08/GB                 |
| No improvement detected                   | No charge (AWS guarantee) |

These charges are **on top of** standard S3 PUT request pricing and normal data-in transfer fees.

## When It Helps vs When It Wastes Money

Transfer Acceleration is beneficial when:
- Users are geographically distributed across multiple continents
- Files are large (>1 GB) and latency compounds without acceleration
- Upload speeds are constrained by long TCP round-trips

Transfer Acceleration adds cost with no benefit when:
- Your users are co-located with the S3 bucket region
- Files are small (<1 MB) where connection overhead dominates, not throughput
- Internal services inside the same AWS region upload to S3 (this is already fast)

## Cost Trap Scenario
A developer enables Transfer Acceleration on a bucket for a temporary test, then forgets to disable it. The application uploads 50 TB/month of internal telemetry data from EC2 instances in the same region.

- Without acceleration: $0 extra (same-region uploads to S3 are free)
- With acceleration enabled: 50,000 GB × $0.04 = $2,000/month in unnecessary charges

The CloudTrail event `PutBucketAccelerateConfiguration` with status `Enabled` marks the start of these charges. Disabling it via the same API or console sets status to `Suspended` and stops billing immediately.

## Checking Acceleration Status
```bash
aws s3api get-bucket-accelerate-configuration --bucket my-bucket
```
Returns `{"Status": "Enabled"}` or an empty response if disabled.

## Alternatives
- CloudFront with S3 origin handles both upload and download acceleration with more granular pricing control
- AWS Global Accelerator for non-HTTP workloads
- Multipart upload + parallel connections often achieves similar throughput without extra cost
