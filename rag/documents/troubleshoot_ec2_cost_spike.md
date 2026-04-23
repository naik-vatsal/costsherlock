# Troubleshooting EC2 Cost Spikes

When EC2 costs increase unexpectedly, work through this checklist systematically. Each item maps to a specific cost driver with a known dollar impact.

## Step 1: Quantify the Spike
In Cost Explorer, set grouping to "Instance Type" and compare the anomaly period to the same period in prior weeks. Note:
- Which instance types increased
- Whether the increase is in On-Demand, Spot, or Reserved usage
- Whether it's hours/count (more instances) or rate (different purchase type)

## Step 2: Auto Scaling Group Runaway

**Check:** EC2 Auto Scaling → Activity History for all ASGs
**Signal:** Unusual scale-out events in the anomaly window
**CloudTrail:** `RunInstances` events with `LaunchTemplate` source
**Cost impact:** Each extra m5.xlarge running for 24 hrs = $4.61

ASG misconfiguration patterns:
- Cooldown period too short → repeated scale-outs
- CloudWatch alarm set on wrong metric → phantom scaling
- Scheduled scaling never scaled back in
- Mixed instance policy changed, adding expensive instance types

## Step 3: Reserved Instance Expiry

**Check:** Cost Explorer → Reserved Instance Utilization report
**Signal:** On-Demand usage increasing for instance types you had reserved
**CloudTrail:** No CloudTrail event — check RI expiry dates in EC2 console
**Cost impact:** m5.xlarge RI expiry = +$50.83/month per instance

## Step 4: Spot Interruption with On-Demand Fallback

**Check:** EC2 → Spot Requests → Interruption notices
**Signal:** Spot costs decrease while On-Demand costs increase for same instance family
**CloudTrail:** `TerminateInstances` (spot interruption) followed by `RunInstances` (on-demand replacement)
**Cost impact:** m5.xlarge: $0.048/hr spot → $0.192/hr on-demand = 4× cost jump

## Step 5: New Instance Launches (Unauthorized or Unexpected)

**Check:** CloudTrail → filter for `RunInstances` events by non-usual IAM users/roles
**Signal:** Unknown principals launching instances
**Cost impact:** Depends on instance type launched

## Step 6: Instance Class Upgrade

**Check:** CloudTrail for `ModifyInstanceAttribute` or instance replacement with larger type
**Signal:** Identical instance count but higher hourly cost
**Cost impact:** m5.xlarge → m5.4xlarge = 4× cost ($140 → $560/month)

## Step 7: Region Change (Instances in Wrong Region)

**Check:** Cost Explorer grouped by Region
**Signal:** New spending in a region not typically used
**Note:** Some regions (e.g., ap-southeast-1) are 15–20% more expensive than us-east-1

## Remediation Priority
1. Stop any unauthorized or unneeded instances immediately (free)
2. Fix ASG configuration to prevent recurrence
3. Renew expiring RIs proactively (before expiry)
4. Review Spot fallback configuration
