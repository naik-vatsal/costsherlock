# AWS Lambda Pricing

Lambda charges on two dimensions: number of requests and duration (GB-seconds of compute consumed). There is a generous free tier that resets monthly.

## Pricing Rates

| Dimension            | Price                   | Free Tier               |
|----------------------|-------------------------|-------------------------|
| Requests             | $0.20 per 1M requests   | 1M requests/month       |
| Duration (x86)       | $0.0000166667/GB-second | 400,000 GB-seconds/month|
| Duration (ARM/Graviton2) | $0.0000133334/GB-second | 400,000 GB-seconds/month|

## Duration Cost Formula
```
Cost = (invocations × duration_seconds × memory_GB) × $0.0000166667
```

### Example 1: Light API Handler
- 10 million invocations/month
- 128 MB memory, 100ms average duration
- Requests: (10M - 1M free) / 1M × $0.20 = $1.80
- Duration: 10M × 0.1s × (128/1024 GB) = 125,000 GB-seconds
  - After free tier (400,000 GB-s): max(0, 125,000 - 400,000) = $0
- **Total: $1.80/month**

### Example 2: Heavy Data Processing
- 5 million invocations/month
- 1024 MB memory, 2 second average duration
- Requests: (5M - 1M) / 1M × $0.20 = $0.80
- Duration: 5M × 2s × 1 GB = 10,000,000 GB-seconds
  - After free tier: 9,600,000 GB-s × $0.0000166667 = **$160/month**
- **Total: ~$160.80/month**

### Example 3: Timeout-Heavy Workload (Cost Trap)
- 1 million invocations/month, all hitting 15-second timeout
- 512 MB memory
- Duration: 1M × 15s × 0.5 GB = 7,500,000 GB-seconds
- Cost: 7,100,000 GB-s × $0.0000166667 = **$118.33/month**
- If bug fixed and duration drops to 0.5s: $0.21/month
- The timeout bug costs $118/month extra

## Lambda Memory and Performance
Lambda allocates CPU proportionally to memory. A 256 MB function runs at 0.25 vCPUs; a 1024 MB function at 1 vCPU; 1769 MB = exactly 1 full vCPU. Doubling memory from 512 MB to 1024 MB often halves execution time, making total GB-seconds cost neutral or cheaper.

## Networking Costs
Lambda does not charge for VPC attachment itself, but functions in a VPC use ENIs and their outbound traffic follows EC2 data transfer pricing. Lambda outside a VPC accessing S3 or DynamoDB in the same region incurs no data transfer charges.
