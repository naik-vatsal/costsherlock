# CloudWatch Logs Pricing

CloudWatch Logs charges for log ingestion, archival storage, and data retrieval. For high-throughput applications, logging costs can become a significant budget line item.

## Pricing

| Dimension                   | Price           |
|-----------------------------|-----------------|
| Log data ingestion          | $0.50/GB        |
| Log data archival (storage) | $0.03/GB-month  |
| Log data retrieved          | $0.01/GB        |
| Insights queries (scanned)  | $0.005/GB scanned |

## Ingestion Cost Examples

**Production web application, INFO-level logging:**
- 1,000 requests/second × 200 bytes/request = 200 KB/s
- Per day: 200 KB/s × 86,400 = ~16.5 GB/day
- Monthly ingestion: 495 GB × $0.50 = **$247.50/month**

**Debug logging accidentally left on:**
- 1,000 requests/second × 2,000 bytes/request (DEBUG level) = 1.65 MB/s
- Per day: 138 GB/day
- Monthly ingestion: 4,140 GB × $0.50 = **$2,070/month**
- Cost of forgetting to turn off DEBUG: $1,822.50/month extra

This is the most common CloudWatch cost trap. A single `UpdateFunctionConfiguration` CloudTrail event setting LOG_LEVEL=DEBUG can trigger a 10× increase in logging costs.

## Storage Accumulation
With no log retention policy set, logs default to **never expire**. Storage charges accumulate indefinitely:
- Ingesting 16.5 GB/day at INFO level
- After 1 year: 6,022 GB stored × $0.03 = $180.66/month just in storage
- After 2 years: 12,045 GB stored × $0.03 = $361.35/month

Setting a 30-day retention policy on all log groups is essentially free (no charge for deletion) and caps storage at ~495 GB = $14.85/month.

## CloudWatch Logs Insights
Querying logs via Insights costs $0.005/GB scanned. A 1-year log archive of 6 TB:
- Single ad-hoc query: 6,000 GB × $0.005 = $30 per query
- Daily dashboards running 10 queries/day: $900/month in query costs alone

## VPC Flow Logs
VPC Flow Logs sent to CloudWatch add ingestion charges. A busy VPC can generate 5–50 GB/hour of flow log data. Sending 10 GB/hour to CloudWatch Logs: 7,200 GB/month × $0.50 = $3,600/month. Sending to S3 instead costs only $0.023/GB-month in storage.
