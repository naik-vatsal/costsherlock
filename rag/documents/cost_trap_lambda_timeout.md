# Cost Trap: Lambda Timeout and Failed Invocation Charges

AWS Lambda charges for the full configured timeout duration when a function times out — even though it produced no useful output. A Lambda function configured with a 15-minute timeout that consistently fails at minute 14 costs almost as much as one that succeeds at minute 14.

## How Lambda Billing Works on Failure

Lambda charges based on **actual duration** rounded up to the nearest millisecond, not on success or failure. If a function runs for 14 minutes and 30 seconds before timing out, you pay for 14 minutes and 30 seconds of GB-seconds.

**Cost of a 15-second timeout, 512 MB function:**
- Duration: 15 seconds
- GB-seconds: 15 × 0.5 GB = 7.5 GB-seconds
- Cost: 7.5 × $0.0000166667 = $0.000125 per invocation

Sounds trivial. At 1 million failed invocations/month:
- 1M × $0.000125 = **$125/month** wasted on timed-out work

**Cost of a 5-minute timeout bug, 1024 MB function:**
- GB-seconds per invocation: 300 × 1 GB = 300 GB-seconds
- Cost per invocation: 300 × $0.0000166667 = $0.005
- At 100,000 invocations/month: **$500/month** wasted
- After fixing to 2-second actual duration: $0.35/month
- **Monthly waste: $499.65**

## The Silent Accumulation Pattern

Lambda timeout bugs often go undetected because:
1. The function appears in logs with a TIMEOUT error
2. Retries (SQS, EventBridge) re-invoke the function — doubling charges
3. DLQ processing adds more invocations
4. CloudWatch shows increased duration metric, but no direct cost alert

SQS-triggered Lambda with 3 retry attempts:
- Each failed message → 4 total invocations (1 original + 3 retries)
- 1M original messages, all timing out: 4M billable invocations at 5 minutes each
- Cost: 4M × $0.005 = **$20,000/month**

## Detection
CloudWatch Lambda metric `Errors` with reason `Timeout` is the primary signal. Correlate with Cost Explorer jump in Lambda spend.

CloudTrail: `UpdateFunctionConfiguration` changing `Timeout` to a high value (e.g., 900 seconds) is a leading indicator of this trap being created.

## Remediation
1. Set timeout to 2–3× expected successful duration, not the maximum
2. Add structured error handling with early exit for unrecoverable states
3. Set CloudWatch alarm on Lambda `Timeout` metric > 0 for critical functions
4. Configure DLQ with notification to prevent infinite retry loops
