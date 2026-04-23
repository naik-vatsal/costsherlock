# NAT Gateway Pricing

NAT Gateways allow EC2 instances in private subnets to access the internet while remaining unreachable from the internet. They are fully managed but carry two separate charges that compound quickly at scale.

## Pricing (us-east-1)

| Charge             | Price               |
|--------------------|---------------------|
| Hourly charge      | $0.045/hr           |
| Data processed     | $0.045/GB (in and out) |

## Monthly Baseline Cost
A single NAT Gateway running 24/7 with no traffic:
- $0.045 × 24 × 30 = **$32.40/month minimum**

Most production architectures deploy one NAT Gateway per Availability Zone for high availability. Three NAT Gateways:
- Baseline: $32.40 × 3 = **$97.20/month before any data transfer**

## Data Processing Cost Examples

**Scenario 1: Microservices calling external APIs**
- 50 instances each pulling 2 GB/day of telemetry/package updates
- Daily data: 100 GB × $0.045 = $4.50/day
- Monthly data cost: **$135/month**
- Plus baseline: $32.40
- **Total single NAT Gateway: $167.40/month**

**Scenario 2: Big Data Pipeline**
- EMR cluster pushing 10 TB/day through NAT Gateway to S3
- Data cost: 10,000 GB × $0.045 × 30 days = **$13,500/month**
- This is the "NAT tax" trap — S3 traffic should use VPC endpoints

**Scenario 3: Cross-AZ Traffic (Hidden Multiplier)**
An EC2 instance in us-east-1a routing traffic through a NAT Gateway in us-east-1b also pays $0.01/GB for cross-AZ data transfer. Total cost per GB: $0.045 (NAT) + $0.01 (cross-AZ) = $0.055/GB.

## The VPC Endpoint Fix
A Gateway VPC Endpoint for S3 is **completely free** — no hourly charge, no data processing fee. Traffic from EC2 to S3 via a VPC endpoint does not pass through the NAT Gateway at all, eliminating both NAT data processing and data transfer costs.

An Interface VPC Endpoint for most other AWS services costs $0.01/hr + $0.01/GB — still 4.5× cheaper per GB than NAT Gateway processing.
