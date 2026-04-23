# Cost Trap: Reserved Instance Expiry

When a Reserved Instance (RI) term ends, AWS silently reverts the matching EC2 or RDS instance to full on-demand pricing. There is no automatic notification unless you have explicitly configured billing alerts.

## The Pricing Cliff

Immediately at RI expiry, the billing rate changes:
- m5.xlarge RI (1-yr All Upfront): $89.33/month equivalent
- m5.xlarge On-Demand (post-expiry): $140.16/month
- **Instant cost increase: +$50.83/month per instance (57% jump)**

For a fleet of 20 × m5.xlarge RIs all expiring simultaneously:
- Before expiry: 20 × $89.33 = $1,786.60/month
- After expiry: 20 × $140.16 = $2,803.20/month
- **Overnight budget hit: +$1,016.60/month (+$12,199.20/year)**

## Why This Happens Silently

1. AWS sends a notification email to the account's root email 30 and 7 days before expiry — but this often goes to a shared inbox that nobody monitors
2. No automatic EC2 stop, no console warning, no default budget alert
3. Instances keep running normally; only the billing line item changes
4. The cost anomaly appears 1–3 days after expiry depending on billing cycle

## RDS Reserved Instance Expiry
Same pattern applies to RDS. A Multi-AZ db.r5.2xlarge:
- Reserved (1-yr All Upfront): ~$1,166/month equivalent
- On-Demand post-expiry: $1,920/month
- **Increase: +$754/month per RDS instance**

## Detecting the Trigger

In Cost Explorer, filter by "Purchase Option: On-Demand" and compare to previous period. An increase in on-demand spend with flat instance count indicates RI expiry.

CloudTrail does not log RI expiry directly, but you can correlate the cost change date with the RI expiry date from the Cost Explorer Reserved Instance utilization report.

## Prevention

1. **AWS Budgets RI expiry alert**: set notification 60 days before end of RI term
2. **Tag instances** with RI expiry date and owner
3. **Cost Explorer RI coverage report**: aim for >90% coverage; sudden drop signals expiry
4. **Auto-renew option**: available for some RI types — evaluate if your workload is stable
5. **Savings Plans**: more flexible alternative — doesn't expire by instance type, auto-applies to matching usage
