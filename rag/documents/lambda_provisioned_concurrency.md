# Lambda Provisioned Concurrency Pricing

Provisioned Concurrency keeps Lambda execution environments initialized and ready to respond instantly, eliminating cold starts. Unlike standard Lambda, provisioned concurrency accrues cost continuously — even with zero invocations.

## Pricing

| Dimension                             | Price                       |
|--------------------------------------|-----------------------------|
| Provisioned Concurrency (allocated)  | $0.000064646/GB-second      |
| Requests (same as standard)          | $0.20 per 1M requests       |
| Duration (while executing)           | $0.000013334/GB-second      |

Note: The duration price for provisioned concurrency executions is **lower** than standard Lambda ($0.0000133 vs $0.0000167), but the idle allocation cost is always running.

## Idle Cost Calculation

Provisioned Concurrency charges you for reserved capacity regardless of traffic.

**Example: 10 provisioned concurrency units, 1024 MB function**
- Idle cost per second: 10 units × 1 GB × $0.000064646 = $0.00064646/second
- Per hour: $2.327
- Per day: $55.85
- Per month: **$1,675.50/month in idle charges alone**

Even if the function receives zero invocations, you pay $1,675.50/month for keeping those environments warm.

## When Provisioned Concurrency Pays Off

Provisioned concurrency is cost-effective when:
- Cold start latency causes real user-facing issues (p99 latency spikes)
- Traffic patterns are predictable and consistent (e.g., steady 8 hrs/day)
- Alternative is over-provisioned EC2 just to avoid cold starts

For intermittent workloads, provisioned concurrency is almost always more expensive than standard Lambda.

## Application Auto Scaling Integration

You can configure Application Auto Scaling to adjust provisioned concurrency on a schedule:
- Scale up from 0 to 10 at 8am weekdays ($55.85 × 22 weekdays/month)
- Scale down to 0 at 6pm — charged only for active hours

This reduces monthly idle cost from $1,675.50 to approximately $550/month for a 10-hour workday schedule.

## Cost Trap: Forgotten Provisioned Concurrency
A common mistake is enabling provisioned concurrency for a performance test and forgetting to remove it. Check Lambda function configurations when investigating unexplained cost increases. The CloudTrail event is `PutFunctionConcurrency` and `PutProvisionedConcurrencyConfig`.
