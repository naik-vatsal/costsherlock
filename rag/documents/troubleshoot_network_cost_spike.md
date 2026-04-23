# Troubleshooting Network and Data Transfer Cost Spikes

Network costs are the most opaque category on an AWS bill. They span multiple services (EC2-Other, VPC, CloudFront) and require correlating Cost Explorer data with VPC Flow Logs.

## Step 1: Locate the Cost in Cost Explorer

Filter by these Usage Types to isolate the source:
- `NatGateway-Bytes` — NAT Gateway data processing
- `NatGateway-Hours` — NAT Gateway hourly charge
- `DataTransfer-Regional-Bytes` — cross-AZ or same-region transfers
- `DataTransfer-Out-Bytes` — internet egress
- `DataTransfer-Out-Bytes (cross-region)` — inter-region transfers
- `VpcEndpoint-Hours` and `VpcEndpoint-Bytes` — interface endpoint usage

## Step 2: NAT Gateway Data Processing Spike

**Signal:** `NatGateway-Bytes` increase without corresponding internet traffic increase
**Root cause:** New workload routing internal traffic through NAT (e.g., EC2 → S3 without endpoint)
**CloudTrail:** `CreateNatGateway` or new `RunInstances` in private subnets accessing AWS services
**Cost impact:** $0.045/GB; 10 TB/month = $450/month

**Fix:** Add S3/DynamoDB Gateway Endpoints (free), evaluate Interface Endpoints for other services.

## Step 3: Cross-AZ Traffic Increase

**Signal:** `DataTransfer-Regional-Bytes` spike
**Root cause:** Microservice or database traffic crossing AZ boundaries more than before
**Cost:** $0.01/GB each direction = $0.02/GB round-trip
**Typical culprits:** ALB routing traffic cross-AZ, ElastiCache client not using cluster-aware clients, RDS read replica in different AZ from application

For 100 TB/month cross-AZ: 100,000 GB × $0.02 = **$2,000/month**

## Step 4: Cross-Region Transfer Spike

**Signal:** `DataTransfer-Out-Bytes` tagged with a non-local region in Cost and Usage Report
**CloudTrail:** `CreateBucketReplication`, `CreateDBInstanceReadReplica` with cross-region, or application code change hitting wrong region endpoint
**Cost:** $0.02/GB; 1 PB/month = $20,480/month

## Step 5: Internet Egress Spike

**Signal:** `DataTransfer-Out-Bytes` from EC2 or S3 to internet jumps significantly
**Root causes:**
- Public S3 bucket being scraped
- EC2 instance exfiltrating data (security incident)
- New feature pushing large payloads to clients
- Video/media content served directly from origin instead of CloudFront

**Investigation:** VPC Flow Logs filtered by destination outside AWS IP ranges, sorted by bytes.

## Step 6: VPN or Direct Connect Bypass

**Signal:** Traffic that was flowing through Direct Connect now going through NAT
**Cause:** Direct Connect circuit failure causing failover to internet path
**Cost impact:** Direct Connect data transfer: $0.02/GB vs NAT + internet egress: $0.135/GB
