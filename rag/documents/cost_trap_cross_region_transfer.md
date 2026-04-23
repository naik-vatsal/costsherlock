# Cost Trap: Hidden Cross-Region Data Transfer

Cross-region data transfer charges are one of the most surprising items on an AWS bill. At $0.02/GB from the source region, they appear as "EC2-Other" or "AmazonS3" line items with no obvious label in cost reports.

## Pricing
- Cross-region data transfer (source charge): $0.02/GB
- Destination region also charges data-in: $0.00 (inbound is free)
- Effective round-trip cost for synchronization: $0.02/GB one-way

## Common Cross-Region Scenarios and Costs

**S3 Cross-Region Replication (CRR):**
An S3 bucket in us-east-1 replicating to eu-west-1 for disaster recovery:
- Data replicated: 10 TB/month
- Transfer cost: 10,000 GB × $0.02 = **$200/month**
- Plus S3 replication request fees: ~$10/month
- Plus destination S3 storage: 10,000 GB × $0.023 = $230/month
- **Total CRR overhead: ~$440/month** on top of source storage

**RDS Cross-Region Read Replicas:**
A db.r5.2xlarge in us-east-1 replicating to us-west-2:
- Replication traffic: ~500 GB/day for a busy OLTP database
- Monthly transfer: 15,000 GB × $0.02 = **$300/month** in transfer alone
- Plus destination RDS instance cost: $0.960/hr ($700.80/month)

**Misconfigured Application Making Cross-Region API Calls:**
A Lambda in us-east-1 calling an SQS queue in us-west-2 instead of the same-region queue:
- 1 million messages/day × 5 KB average = 5 GB/day
- Monthly: 150 GB × $0.02 = **$3/month** (small but indicative of configuration error)
- Fixing the region config: $0/month

## Detection

Cross-region transfer appears in Cost Explorer under:
- Service: EC2 → Usage Type contains "DataTransfer-Regional" or "DataTransfer-Out"
- Service: S3 → Usage Type contains "DataTransfer-Out-Bytes"

CloudTrail events that indicate cross-region activity:
- `CreateBucketReplication` on S3
- `CreateDBInstanceReadReplica` with cross-region parameter
- Lambda or EC2 API calls to endpoints in non-local regions

## Identifying the Source
Use VPC Flow Logs filtered by destination IP ranges of other AWS regions, or use AWS Cost and Usage Report with `lineItem/UsageType` containing region codes to pinpoint which resources generate cross-region traffic.
