# Troubleshooting Lambda Cost Spikes

Lambda cost spikes come from more invocations, longer durations, higher memory, or runaway concurrency. The key is identifying which dimension changed using CloudWatch metrics.

## Step 1: Identify the Dimension

Cost Explorer → filter Service: Lambda → group by Usage Type:
- `Lambda-GB-Second` — duration × memory (the primary cost driver)
- `Lambda-Request` — invocation count

Check CloudWatch Lambda service metrics for the affected function:
- `Invocations` — call count over time
- `Duration` (p50, p99) — execution time distribution
- `Errors` and `Throttles` — failure patterns
- `ConcurrentExecutions` — parallelism level

## Step 2: Invocation Volume Spike

**Signal:** `Lambda-Request` cost up, `Lambda-GB-Second` proportionally up
**Common causes:**
- Upstream service sending more events (SQS queue depth increase)
- EventBridge rule firing more frequently
- API Gateway traffic spike
- Runaway retry loop from a downstream failure

**CloudTrail:** `CreateEventSourceMapping` or `UpdateEventSourceMapping` changes affecting batch size or parallelism factor
**Cost at scale:** 100M invocations × $0.20/1M = $20 in requests alone, but if duration is 1s at 512 MB: +$850

## Step 3: Duration Regression

**Signal:** `Duration` p99 increased significantly, same invocation count
**Common causes:**
- Downstream service latency increased (DB, external API)
- Timeout set too high, masking slow code paths
- Memory reduced, causing slower CPU execution
- New code path with O(n²) complexity

**CloudTrail:** `UpdateFunctionCode` or `UpdateFunctionConfiguration` immediately before duration increase
**Cost impact:** Duration 100ms → 2,000ms at 512 MB, 10M invocations: $0.83 → $16.67/month

## Step 4: Memory Increase Without Duration Benefit

**Signal:** `Lambda-GB-Second` up while `Duration` stayed flat
**CloudTrail:** `UpdateFunctionConfiguration` with higher `memorySize`
**Cost impact:** 512 MB → 3,008 MB (max): 5.875× higher GB-second cost per invocation

## Step 5: Provisioned Concurrency Added

**Signal:** Lambda cost non-zero even during zero-traffic hours
**Check:** Lambda console → function → Configuration → Concurrency → Provisioned concurrency
**Cost impact:** 10 units × 1 GB × $0.000064646 × 730 hrs = $472/month idle
**CloudTrail:** `PutProvisionedConcurrencyConfig`

## Step 6: Recursive Invocation Bug

**Signal:** Invocations growing exponentially per hour
**Pattern:** Function A invokes Function B which invokes Function A
**Cost impact:** Can exhaust $10,000 budget in hours if unchecked

Immediate action: Set Lambda reserved concurrency to 0 to stop runaway function while debugging.
