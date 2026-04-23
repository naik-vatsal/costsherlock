# RDS Instance Pricing

Amazon RDS charges per instance-hour based on the database engine, instance class, and deployment configuration. All prices below are for MySQL/PostgreSQL in us-east-1.

## db.t3 General Purpose (Burstable)
- db.t3.micro: $0.017/hr ($12.41/month) — free tier eligible
- db.t3.small: $0.034/hr ($24.82/month)
- db.t3.medium: $0.068/hr ($49.64/month)
- db.t3.large: $0.136/hr ($99.28/month)
- db.t3.xlarge: $0.272/hr ($198.56/month)
- db.t3.2xlarge: $0.544/hr ($397.12/month)

## db.m5 General Purpose
- db.m5.large: $0.171/hr ($124.83/month)
- db.m5.xlarge: $0.342/hr ($249.66/month)
- db.m5.2xlarge: $0.684/hr ($499.32/month)
- db.m5.4xlarge: $1.368/hr ($998.64/month)
- db.m5.8xlarge: $2.736/hr ($1,997.28/month)

## db.r5 Memory Optimized
- db.r5.large: $0.240/hr ($175.20/month)
- db.r5.xlarge: $0.480/hr ($350.40/month)
- db.r5.2xlarge: $0.960/hr ($700.80/month)
- db.r5.4xlarge: $1.920/hr ($1,401.60/month)
- db.r5.8xlarge: $3.840/hr ($2,803.20/month)
- db.r5.16xlarge: $7.680/hr ($5,606.40/month)

## Multi-AZ Deployment Surcharge
Multi-AZ doubles the instance cost because AWS runs a synchronous standby replica in a second Availability Zone. **The standby is not accessible for reads** — it exists only for failover.

- db.m5.xlarge Single-AZ: $0.342/hr ($249.66/month)
- db.m5.xlarge Multi-AZ: $0.684/hr ($499.32/month)

Accidentally enabling Multi-AZ on a non-critical development database adds $249.66/month for zero additional usable capacity.

## Engine-Specific Pricing
Oracle and SQL Server carry license fees. SQL Server Web edition costs ~2.3× the MySQL price on the same instance class. Oracle EE with BYOL is cheaper than license-included.

## Reserved RDS Instances
- db.m5.xlarge 1yr All Upfront: ~$1,784 ($148.67/month) — 40% savings vs on-demand
- db.r5.2xlarge 1yr All Upfront: ~$5,248 ($437.33/month) — 37% savings vs on-demand
