# VPC Endpoint Pricing

VPC Endpoints allow EC2 instances to communicate with AWS services without traversing the public internet or a NAT Gateway. They eliminate NAT Gateway data processing fees and can dramatically reduce monthly bills.

## Endpoint Types and Pricing

### Gateway Endpoints (S3 and DynamoDB only)
- **Price: $0.00 — completely free**
- No hourly charge, no data processing fee
- Traffic between EC2 and S3/DynamoDB stays on the AWS network
- Simply attach to route tables; no DNS changes needed

### Interface Endpoints (most other AWS services)
- **Hourly: $0.01/hr per AZ**
- **Data processing: $0.01/GB**
- One endpoint per AZ for HA = $0.02/hr ($14.40/month baseline for 2 AZs)

## Cost Comparison: NAT Gateway vs VPC Endpoints

**Workload: 10 TB/month of S3 traffic from private EC2 instances**

| Route             | Hourly Cost    | Data Cost              | Monthly Total  |
|-------------------|----------------|------------------------|----------------|
| NAT Gateway (1 AZ)| $0.045/hr ($32.85/mo) | 10,000 GB × $0.045 = $450 | **$482.85** |
| S3 Gateway Endpoint| $0.00/hr      | $0.00                  | **$0.00**     |
| Monthly Savings   | —              | —                      | **$482.85**   |

**Workload: 10 TB/month of SQS/SNS/other AWS service traffic**

| Route             | Monthly Total  |
|-------------------|----------------|
| NAT Gateway       | $482.85        |
| Interface Endpoint (2 AZs) | $14.40 baseline + $100 data = **$114.40** |
| Monthly Savings   | **$368.45**    |

## Common Interface Endpoint Candidates
Services worth evaluating for Interface Endpoints based on traffic volume:
- SQS/SNS: $0.01/hr + $0.01/GB vs $0.045/GB through NAT
- ECR (Docker image pulls): large images (500 MB–2 GB) benefit greatly
- Secrets Manager: frequent secret reads from private Lambda/EC2
- SSM: Systems Manager agent traffic from private instances
- CloudWatch Logs: log delivery from private EC2

## Calculating Break-Even
Interface endpoint break-even vs NAT Gateway data cost:
- Fixed endpoint cost: $14.40/month (2 AZs)
- Per GB savings: $0.045 (NAT) − $0.01 (endpoint) = $0.035/GB
- Break-even: $14.40 / $0.035 = **411 GB/month**
- Any service sending over 411 GB/month through NAT Gateway is worth an Interface Endpoint.
