# Cost Trap: NAT Gateway Data Processing

The NAT Gateway trap is the most common source of unexpected AWS networking bills. It occurs when private EC2 instances route high-volume traffic to AWS services (S3, DynamoDB, SQS) through a NAT Gateway instead of VPC endpoints.

## How the Trap Works

Every byte that flows through a NAT Gateway costs $0.045/GB — both inbound to the NAT Gateway from the internet AND outbound from private instances. For traffic within AWS (e.g., EC2 to S3), both legs count:
1. EC2 → NAT Gateway: $0.045/GB (data processed out of NAT)
2. NAT → S3 (internet): $0.09/GB (data transfer to internet)

Wait — S3 is not on the internet from AWS's perspective if you use a Gateway Endpoint. Without one, traffic from a private subnet to S3 goes: EC2 → NAT Gateway → Internet Gateway → S3. The NAT Gateway charges for every GB of this traffic.

## Typical Impact

A data pipeline running nightly, copying 2 TB from RDS to S3:
- NAT Gateway data processing: 2,000 GB × $0.045 = $90/night
- Monthly: $2,700/month just for the copy job
- With a free S3 Gateway Endpoint: $0/month

An application server fleet of 50 × m5.large instances pulling Docker images from ECR (~2 GB per deployment) with 10 deployments/week:
- Monthly ECR pull data: 50 × 2 GB × 40 = 4,000 GB
- NAT cost: 4,000 GB × $0.045 = **$180/month**
- With ECR Interface Endpoint: $14.40/month + $0.01/GB = $54.40/month

## Detection Signals
- CloudWatch metric `BytesOutToDestination` on the NAT Gateway spikes
- Cost Explorer showing sudden jump in "EC2-Other" line item for "NatGateway"
- CloudTrail: absence of `CreateVpcEndpoint` events for S3/DynamoDB despite heavy usage

## Remediation
1. Create free S3 and DynamoDB Gateway Endpoints in 2 minutes — zero disruption
2. Evaluate Interface Endpoints for ECR, SQS, SNS, Secrets Manager
3. Set a CloudWatch alarm on `BytesOutToDestination` with threshold at 10% above baseline
4. Review NAT Gateway usage monthly with VPC Flow Logs

Break-even for S3 Gateway Endpoint: immediate — it is free with no traffic threshold required.
