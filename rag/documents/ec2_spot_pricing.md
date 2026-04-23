# EC2 Spot Instance Pricing

Spot Instances use spare EC2 capacity at discounts of 60–90% off on-demand prices. The trade-off is a 2-minute interruption notice when AWS reclaims the capacity.

## Example Spot Prices (us-east-1, approximate)
- m5.xlarge: ~$0.048/hr (vs $0.192 on-demand) — 75% savings
- c5.2xlarge: ~$0.085/hr (vs $0.340 on-demand) — 75% savings
- r5.4xlarge: ~$0.252/hr (vs $1.008 on-demand) — 75% savings
- g4dn.xlarge: ~$0.157/hr (vs $0.526 on-demand) — 70% savings

Spot prices fluctuate based on supply and demand per Availability Zone. Prices are generally stable for days or weeks before a spike.

## Interruption Risk by Instance Pool
Interruption frequency varies. AWS provides a Spot Instance Advisor showing:
- < 5% interruption rate: common for m5.large, c5.large in low-demand pools
- 5–10% rate: m5.xlarge in crowded AZs during peak hours
- > 20% rate: GPU instances during ML training peaks

## Cost Calculation Example
Running a batch job on 10 × c5.2xlarge:
- On-demand: 10 × $0.340 × 6 hours = $20.40
- Spot: 10 × $0.085 × 6 hours = $5.10
- Savings: $15.30 per batch run ($5,600/year if run daily)

## When Spot Is Appropriate
- Stateless batch processing
- Big data / EMR clusters
- CI/CD build agents
- Model training (checkpointing required)
- Rendering farms

## When Spot Is Dangerous
- Databases (interruption causes downtime)
- Real-time customer-facing services without fallback
- Single-instance deployments without ASG replacement logic

## Spot Fleet and ASG Integration
Spot instances are best managed via Auto Scaling Groups with mixed instance policies. Configure `SpotAllocationStrategy: capacity-optimized` to select pools with lowest interruption risk. Always specify at least 3 instance types and 2 AZs to maintain availability during capacity crunches.

If a spot interruption causes an ASG to replace with on-demand, the on-demand price applies from that point. A fleet of 20 spots interrupted and replaced with on-demand m5.xlarge costs $0.192/hr each vs $0.048/hr — a 4× cost jump that can look like an anomaly in Cost Explorer.
