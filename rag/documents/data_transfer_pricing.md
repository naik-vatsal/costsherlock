# AWS Data Transfer Pricing

Data transfer is one of the most misunderstood cost categories in AWS. The fundamental rule: data flowing **into** AWS is free; data flowing **out** is charged.

## Internet Egress (EC2/S3 to Internet)

| Volume per Month | Price/GB   |
|------------------|-----------|
| First 100 GB     | $0.00 (free) |
| 100 GB – 10 TB   | $0.09/GB  |
| 10 TB – 50 TB    | $0.085/GB |
| 50 TB – 150 TB   | $0.07/GB  |
| 150 TB+          | $0.05/GB  |

A video streaming service serving 500 TB/month:
- First 100 GB: $0
- Next 9,900 GB: $0.09 × 9,900 = $891
- Next 40,000 GB: $0.085 × 40,000 = $3,400
- Next 100,000 GB: $0.07 × 100,000 = $7,000
- Remaining 350,000 GB: $0.05 × 350,000 = $17,500
- **Total egress: $28,791/month**

## Cross-Region Data Transfer
Transferring data between AWS regions costs $0.02/GB from the source region. This applies to:
- S3 replication between regions
- EC2 to EC2 cross-region communication
- RDS cross-region read replicas (data sync traffic)

## Cross-AZ Data Transfer
Data transferred between Availability Zones within the same region costs **$0.01/GB in each direction** ($0.02/GB round-trip). This is a commonly overlooked charge for microservice architectures where services span AZs.

A service making 1 million cross-AZ calls/day at 10 KB average payload:
- Daily cross-AZ data: 1M × 10 KB = 10 GB
- Monthly: 300 GB × $0.01 = **$3/month** (surprisingly cheap, but compounds with volume)

## CloudFront as Cost Reducer
CloudFront egress to internet is cheaper than direct EC2/S3 egress:
- CloudFront to internet: $0.0085–$0.085/GB depending on region
- For US/EU: $0.0085/GB (10× cheaper than EC2 direct)

Serving 500 TB/month via CloudFront from US: ~$4,250/month vs $28,791 direct.

## Data Transfer "Free" Scenarios
- EC2 to S3 in the same region: **Free**
- EC2 to DynamoDB in the same region: **Free**
- EC2 to EC2 in the same AZ using private IP: **Free**
- Inbound data from internet: **Free**
