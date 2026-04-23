# EC2 On-Demand Instance Pricing

EC2 On-Demand pricing requires no upfront commitment and bills per second (minimum 60 seconds) for Linux instances. Prices vary by region; all figures below are for us-east-1.

## T3 General Purpose (Burstable)
- t3.nano: $0.0052/hr ($3.80/month)
- t3.micro: $0.0104/hr ($7.59/month)
- t3.small: $0.0208/hr ($15.18/month)
- t3.medium: $0.0416/hr ($30.37/month)
- t3.large: $0.0832/hr ($60.74/month)
- t3.xlarge: $0.1664/hr ($121.47/month)
- t3.2xlarge: $0.3328/hr ($242.94/month)

T3 instances use CPU credits. When credits are exhausted, unlimited mode charges an additional $0.05/vCPU-hour for sustained usage above baseline.

## C5 Compute Optimized
- c5.large: $0.085/hr ($62.05/month)
- c5.xlarge: $0.170/hr ($124.10/month)
- c5.2xlarge: $0.340/hr ($248.20/month)
- c5.4xlarge: $0.680/hr ($496.40/month)
- c5.9xlarge: $1.530/hr ($1,116.90/month)
- c5.18xlarge: $3.060/hr ($2,233.80/month)

C5 instances use Intel Xeon Platinum processors and are suited for CPU-intensive workloads like batch processing and gaming.

## M5 General Purpose
- m5.large: $0.096/hr ($70.08/month)
- m5.xlarge: $0.192/hr ($140.16/month)
- m5.2xlarge: $0.384/hr ($280.32/month)
- m5.4xlarge: $0.768/hr ($560.64/month)
- m5.8xlarge: $1.536/hr ($1,121.28/month)
- m5.16xlarge: $3.072/hr ($2,242.56/month)

## R5 Memory Optimized
- r5.large: $0.126/hr ($91.98/month)
- r5.xlarge: $0.252/hr ($183.96/month)
- r5.2xlarge: $0.504/hr ($367.92/month)
- r5.4xlarge: $1.008/hr ($735.84/month)
- r5.8xlarge: $2.016/hr ($1,471.68/month)
- r5.16xlarge: $4.032/hr ($2,943.36/month)

## Key Cost Drivers
Running an m5.4xlarge 24/7 costs $561/month on-demand. The same workload on a 1-year Reserved Instance (all upfront) costs ~$340/month — a 39% saving. Leaving a fleet of c5.2xlarge instances running overnight during development adds $0.34/hr per instance; 10 instances left running for a 12-hour weekend accumulates $40.80 in unplanned spend.

Always check instance utilization in CloudWatch before sizing. Average CPU under 10% for 14 days is a strong signal to downsize.
