# Reserved Instance Planning

Reserved Instances require careful planning — commit too early and you're locked into the wrong instance type; commit too late and you overpay on-demand. The break-even analysis determines when buying an RI makes financial sense.

## Break-Even Analysis

For a 1-year RI to save money, the instance must run long enough that the RI total cost falls below what on-demand would have cost.

**m5.xlarge us-east-1, 1-year All Upfront:**
- RI total cost: $1,072 (paid upfront)
- On-demand hourly: $0.192/hr
- Break-even hours: $1,072 / $0.192 = 5,583 hours
- Break-even percentage: 5,583 / 8,760 = **63.7% utilization needed**

If the instance runs > 63.7% of the year (5,583+ hours), the RI saves money.

**1-year No Upfront (no cash required):**
- Effective rate: $94.84/month ($0.13/hr)
- On-demand: $0.192/hr
- At 100% utilization: saves $0.062/hr = $543/year

## 1-Year vs 3-Year Comparison

m5.xlarge, All Upfront:
| Term | Total Cost | Effective Rate | Savings vs On-Demand |
|------|-----------|----------------|---------------------|
| On-Demand | $1,681/yr | $0.192/hr | — |
| 1-Year | $1,072/yr | $0.122/hr | 36% |
| 3-Year | $1,893/3yr = $631/yr | $0.072/hr | 62% |

3-year RIs save 26% more than 1-year — but lock you in for 3 years. Use 3-year only for stable, foundational infrastructure (database servers, core API instances).

## Portfolio Approach

The standard RI strategy:
- **60% of baseline** → 3-year All Upfront (maximum savings, stable workloads)
- **20% of baseline** → 1-year Partial Upfront (flexibility for workloads that might change)
- **20% buffer** → On-Demand (handle unexpected growth)

For a fleet of 100 × m5.xlarge running 24/7:
- 60 × 3-year RI: 60 × $631/yr = $37,860/yr
- 20 × 1-year RI: 20 × $1,094/yr = $21,880/yr
- 20 × On-Demand: 20 × $1,681/yr = $33,620/yr
- **Total: $93,360/yr**
- All on-demand: 100 × $1,681 = $168,100/yr
- **Savings: $74,740/yr (44% reduction)**

## RI Coverage Targets

AWS recommends 80%+ RI coverage for steady-state workloads. Check Cost Explorer → Reserved Instance Coverage report.

Under-coverage: On-Demand costs are higher than necessary. Buy more RIs.
Over-coverage: Idle RIs — still paid for, no benefit. Sell on Marketplace or accept the loss.
