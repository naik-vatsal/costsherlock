# EC2 Auto Scaling Groups and Cost Impact

Auto Scaling Groups (ASGs) automatically adjust EC2 fleet size based on metrics, schedules, or predictive policies. Every scale-out event increases EC2 costs; misconfigured ASGs are a frequent source of unexpected bills.

## How ASG Triggers Costs

Scale-out adds instances billed at the full on-demand (or spot) rate from the moment they launch. An ASG configured to scale on CPU > 60% that launches 5 × m5.xlarge instances adds:
- 5 × $0.192/hr = $0.96/hr while scaled out
- If scaled out for 8 hours/day on average: $0.96 × 8 × 30 = $230/month incremental

## Cooldown Periods
Cooldown is the time (in seconds) the ASG waits after a scale-out before it can scale out again. Default cooldown is 300 seconds (5 minutes).

**The cost trap:** If cooldown is set too low (e.g., 60 seconds) and a bursty workload keeps triggering scale-out, the ASG can overshoot the desired capacity significantly. 20 unnecessary instances at m5.large = $0.096 × 20 = $1.92/hr of wasted spend.

Scale-in cooldown controls when instances are terminated after a scale-in trigger. If set too high, you over-pay for idle instances. Setting scale-in cooldown to 600 seconds vs 120 seconds can mean 8 extra idle m5.large minutes per scale-in event at $0.096/hr.

## Scheduled Scaling
A dev ASG left at business-hours-only scaling that was never configured:
- Running 10 × m5.large 24/7: $0.096 × 10 × 24 × 30 = $691/month
- Running 10 × m5.large 8 hrs/day (scaled to 1 at night): $0.096 × 10 × 8 × 30 + $0.096 × 1 × 16 × 30 = $230 + $46 = $276/month
- Savings from scheduled scaling: $415/month

## Target Tracking vs Step Scaling
Target tracking (e.g., maintain 50% CPU) is more responsive and tends to over-provision less than step scaling with poorly tuned thresholds.

## CloudTrail Signals
ASG scale-out events appear in CloudTrail as `CreateAutoScalingGroup`, `UpdateAutoScalingGroup`, and EC2 `RunInstances` events. A sudden burst of `RunInstances` calls correlated with a cost spike is a strong signal that an ASG fired unexpectedly — check the scaling activity history in the console or via `describe-scaling-activities` API.
