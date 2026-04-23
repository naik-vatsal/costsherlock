# S3 Request Pricing

S3 charges for API requests independently of storage. For high-throughput workloads, request costs can exceed storage costs significantly.

## Request Prices (us-east-1)

| Request Type                     | Price           |
|----------------------------------|-----------------|
| PUT, COPY, POST, LIST            | $0.005 per 1,000 requests |
| GET, SELECT, and all others      | $0.0004 per 1,000 requests |
| DELETE requests                  | Free            |
| Lifecycle transition requests    | $0.01 per 1,000 transitions |
| S3 Select (data scanned)         | $0.002 per GB scanned |
| S3 Select (data returned)        | $0.0007 per GB returned |

## Standard-IA and Glacier Request Premiums
- Standard-IA GET: $0.01/1,000 (25× more than Standard GET)
- Glacier Instant Retrieval GET: $0.03/1,000
- Glacier Flexible standard retrieval: $0.01/GB + per-request fees
- Deep Archive retrieval: $0.02/GB (bulk) or $0.10/GB (standard)

## Cost Examples at Scale

**Image CDN serving 100 million GET requests/month:**
- GET cost: 100,000,000 / 1,000 × $0.0004 = $40/month in requests alone

**Data pipeline doing 50 million PUT requests/month:**
- PUT cost: 50,000,000 / 1,000 × $0.005 = $250/month in requests alone

**Misconfigured application hitting LIST repeatedly:**
- 10 million LIST calls/day × 30 = 300 million/month
- Cost: 300,000,000 / 1,000 × $0.005 = $1,500/month from LIST alone

## Data Transfer Out of S3
- First 100 GB/month: Free (to internet)
- Next 9.9 TB: $0.09/GB
- Next 40 TB: $0.085/GB
- Next 100 TB: $0.07/GB
- Over 150 TB: $0.05/GB

Data transfer between S3 and EC2 in the **same region** is free. Cross-region data transfer from S3 costs $0.02/GB (source region charge).

## Transfer Acceleration Surcharge
S3 Transfer Acceleration adds $0.04–$0.08/GB on top of standard transfer pricing. For a workload transferring 10 TB/month, Transfer Acceleration adds $400–$800/month. Ensure this feature is intentionally enabled; check CloudTrail for `PutBucketAccelerateConfiguration` events.
