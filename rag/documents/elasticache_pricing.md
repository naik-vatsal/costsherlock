# ElastiCache Pricing

Amazon ElastiCache for Redis and Memcached charges per node-hour based on the node type. Pricing is similar to EC2 in structure — on-demand, reserved, and (for some types) serverless options.

## Redis On-Demand Node Pricing (us-east-1)

| Node Type       | Price/hr    | Monthly (730 hrs)  |
|-----------------|-------------|-------------------|
| cache.t3.micro  | $0.017/hr   | $12.41             |
| cache.t3.small  | $0.034/hr   | $24.82             |
| cache.t3.medium | $0.068/hr   | $49.64             |
| cache.r6g.large | $0.154/hr   | $112.42            |
| cache.r6g.xlarge| $0.308/hr   | $224.84            |
| cache.r6g.2xlarge| $0.616/hr  | $449.68            |
| cache.r6g.4xlarge| $1.232/hr  | $899.36            |
| cache.r6g.8xlarge| $2.464/hr  | $1,798.72          |
| cache.m6g.large | $0.128/hr   | $93.44             |
| cache.m6g.xlarge| $0.256/hr   | $186.88            |

## Cluster Mode and Replication Costs
ElastiCache Redis with Multi-AZ and replication multiplies node costs:
- A cluster with 1 primary + 2 read replicas = 3 billable nodes
- 3 × cache.r6g.xlarge = 3 × $0.308 = $0.924/hr ($674.52/month)

Cluster Mode with 3 shards × 3 nodes = 9 total nodes:
- 9 × cache.r6g.xlarge = $2.772/hr ($2,023.56/month)

## ElastiCache Serverless (Redis)
- Compute: $0.0034 per ECPU-hour
- Storage: $0.125/GB-hour
- Minimum viable workload at 1 ECPU idle: ~$2.48/month
- A busy cache at 1,000 ECPUs: $2,482/month

Serverless is cost-effective for unpredictable or intermittent workloads. For steady, high-throughput caches, reserved instances offer better economics.

## Reserved Instance Savings
cache.r6g.xlarge 1-year All Upfront:
- On-demand: $0.308/hr ($224.84/month)
- Reserved: ~$0.195/hr ($142.35/month)
- Savings: 37%

## Backup Storage
ElastiCache automated backups store snapshots in S3. Storage equal to 100% of node capacity is free; additional backup storage is $0.085/GB-month. A 100 GB cache with daily snapshots and 7-day retention: the first 100 GB is free, any incremental data beyond that is charged.
