# ECS Fargate Pricing

AWS Fargate is a serverless compute engine for containers. You pay for vCPU and memory allocated to your task, billed per second with a 1-minute minimum. There is no EC2 instance charge — only the task resource allocation.

## Pricing (us-east-1, Linux/x86)

| Resource     | On-Demand Price         | Spot Price              |
|--------------|-------------------------|-------------------------|
| vCPU         | $0.04048/vCPU-hour      | $0.01619/vCPU-hour      |
| Memory (GB)  | $0.004445/GB-hour       | $0.00178/GB-hour        |

## Task Cost Examples

**Small web API task: 0.5 vCPU, 1 GB memory**
- vCPU: 0.5 × $0.04048 = $0.02024/hr
- Memory: 1 × $0.004445 = $0.004445/hr
- Total: $0.024685/hr ($18.02/month per task)
- 10 tasks for HA: **$180.20/month**

**Data processing task: 2 vCPU, 8 GB memory**
- vCPU: 2 × $0.04048 = $0.08096/hr
- Memory: 8 × $0.004445 = $0.03556/hr
- Total: $0.11652/hr ($85.06/month per task)

**ML inference task: 4 vCPU, 16 GB memory**
- vCPU: 4 × $0.04048 = $0.16192/hr
- Memory: 16 × $0.004445 = $0.07112/hr
- Total: $0.23304/hr ($170.12/month per task)

## Fargate Spot Savings
The same 4 vCPU / 16 GB task on Fargate Spot:
- vCPU: 4 × $0.01619 = $0.06476/hr
- Memory: 16 × $0.00178 = $0.02848/hr
- Total: $0.09324/hr ($68.06/month) — **60% savings**

Fargate Spot tasks can be interrupted with 2 minutes notice, same as EC2 Spot.

## ECS vs EC2 Cost Comparison
Running 20 × (2 vCPU, 8 GB) tasks:
- Fargate: 20 × $0.11652 = $2.33/hr ($1,701.20/month)
- EC2 m5.xlarge (4 vCPU, 16 GB): $0.192/hr, 2 tasks per instance = 10 instances × $0.192 = $1.92/hr ($1,401.60/month)
- EC2 is 18% cheaper but requires managing instance lifecycle, patching, and capacity

## ARM/Graviton2 Pricing
Fargate on ARM (Graviton2) is 20% cheaper:
- vCPU: $0.03238/vCPU-hour
- Memory: $0.00356/GB-hour
Use ARM-compatible container images to reduce costs by 20% with no code changes for most workloads.
