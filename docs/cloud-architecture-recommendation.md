# Cloud Architecture Recommendation

Pricing snapshot: 2026-04-24. Prices are public USD list prices, before tax, support, domain registration, and unusual bandwidth. This document treats "monolithic" as one repository, one deployable platform boundary, one operational runbook, and no managed replacement for Airflow or Prefect unless explicitly noted.

## Recommendation

Use a single DigitalOcean Basic Droplet running the existing Docker Compose stack:

- Caddy terminates HTTPS and routes `raniendu.dev`, `prefect.raniendu.dev`, `raman.raniendu.dev`, and `flow.raniendu.dev`.
- DotDev, Prefect Server, Prefect worker, Raman, Airflow webserver, Airflow scheduler, and one shared PostgreSQL container run on the same host.
- GitHub Actions deploys by SSH to `/opt/platform`.
- Terraform creates the Droplet, firewall, SSH key attachment, and outputs the public IP for DNS.
- Production now runs on `s-1vcpu-2gb`; resize upward only if Airflow, Prefect, Raman, or local Postgres memory pressure shows up in metrics.

Estimated monthly cost:

| Item | Monthly cost |
| --- | ---: |
| DigitalOcean Basic Droplet, 1 vCPU / 2 GiB / 50 GiB SSD | $12.00 |
| Weekly Droplet backups, percentage plan | $2.40 |
| Total | $14.40 |

This is the best practical option for the current monorepo because it is the cheapest DigitalOcean architecture, preserves Docker Compose, avoids managed database minimums, avoids Airflow service rewrites, and keeps deployment simple. AWS Lightsail can be a close cost competitor if snapshot storage stays small, but the expected monthly difference is only a few dollars and does not justify moving away from the DigitalOcean/Terraform path already built unless there is a separate reason to standardize on AWS.

## DigitalOcean Design

Target runtime:

```text
Internet
  |
  v
DigitalOcean Firewall: 80/443 public, 22 restricted
  |
  v
Caddy on one Droplet
  |-- raniendu.dev          -> dotdev:8501
  |-- prefect.raniendu.dev  -> prefect-server:4200, Caddy basic auth
  |-- raman.raniendu.dev    -> raman:8000
  |-- jaeger.raniendu.dev   -> jaeger:16686, Caddy basic auth
  |-- flow.raniendu.dev     -> airflow-webserver:8080

Docker Compose network
  |-- dotdev
  |-- prefect-server
  |-- prefect-worker
  |-- raman
  |-- jaeger
  |-- platform-postgres
  |-- airflow-webserver
  |-- airflow-scheduler
  |-- shared postgres volume
  |-- raman state volume
  |-- airflow logs/config/plugin volumes
```

Operational choices:

- Keep PostgreSQL local in one container. Managed databases add cost and are unnecessary for this personal platform unless restore time or database isolation becomes more important than monthly spend.
- Enable weekly Droplet backups immediately. Add logical `pg_dump` backups later if the data becomes important enough to need app-level restore instead of whole-host restore.
- Keep only Caddy public. Prefect is additionally protected with Caddy basic auth. Airflow relies on its own login and should still be treated as an admin surface.
- For future replacement migrations, keep the previous live resource in place until the new endpoints are verified after DNS cutover and decommissioning is explicitly approved.

## DigitalOcean Alternatives

| Option | Shape | Estimate | Assessment |
| --- | --- | ---: | --- |
| Single 2 GiB Droplet | All services in one Compose stack after Postgres consolidation | $14.40/mo with weekly backups | Current production shape. Cheapest simple DigitalOcean option that preserves the current architecture. |
| Single 4 GiB Droplet | All services in one Compose stack | $28.80/mo with weekly backups | Safe fallback if the 2 GiB host shows sustained memory pressure. |
| Two Droplets | 2 GiB web/Prefect Droplet plus 4 GiB Airflow Droplet | $43.20/mo with weekly backups | Useful only if Airflow needs isolation. Less monolithic and more operations. |
| Single 8 GiB Droplet | Same as recommended, more headroom | $57.60/mo with weekly backups | Good upgrade path, not the starting point. |
| App Platform for DotDev/Prefect plus Airflow Droplet | DotDev service, Prefect service/worker, Postgres, Airflow Droplet | Roughly $60.80-$68.80/mo minimum | Easier web deploys, but more expensive and less monolithic. Development database is not a production-grade backup story. |
| App Platform only | All services on App Platform | Not viable | App Platform has ephemeral local filesystem and no mounted volumes, which does not fit Airflow logs, scheduler state, and local Postgres. |
| DigitalOcean Functions | Move some jobs to functions | Can be very cheap for small jobs | Not viable for the core stack: max 15 minutes, max 1 GiB memory, no long-running web UI/scheduler. |

## Serverless Options

Serverless is attractive only for workloads that are stateless, event-driven, and can stop when idle. This stack has four always-on surfaces: DotDev, Prefect API/UI, Raman, and Airflow API/scheduler. DotDev could be made serverless later. Airflow, Prefect, and Raman are the cost drivers because they want persistent runtime state, metadata, local storage, workers, logs, or web UI.

DigitalOcean:

- App Platform can run services, workers, and jobs and starts at low per-container prices. It is reasonable for DotDev and possibly Prefect, but not a good Airflow home because local filesystem state is ephemeral and volumes are not supported.
- Functions include a free monthly allowance and cheap usage-based pricing, but the timeout and memory limits make them a fit for small webhooks or simple scheduled jobs, not Airflow or Prefect Server.

AWS:

- Lambda plus EventBridge Scheduler is the cheapest way to run isolated scheduled Python tasks. It is not a drop-in replacement for Airflow because Lambda has a 15-minute timeout and no persistent Airflow UI/scheduler.
- App Runner is good for individual web containers, but each always-warm service has its own baseline charge. DotDev could fit; Prefect plus workers plus database becomes more expensive and less monolithic.
- ECS Fargate removes server management but is not cheap for an always-running monolith. A single 2 vCPU / 4 GiB Linux task is roughly $73/mo before load balancer, database, storage, logs, and public IPv4.
- MWAA Serverless can be cheap for AWS-managed task usage, but it changes the Airflow operating model. Provisioned MWAA is not cost-effective here; AWS's own small-environment example is about $449/mo.

Google Cloud:

- Cloud Run is the strongest serverless fit for DotDev. It can scale to zero and has a useful free tier.
- Cloud Run Jobs could replace some Prefect scheduled work, but then Prefect becomes less central.
- Cloud Run worker pools can run background workers, but a worker that must stay alive is still charged for continuous instance time.
- Managed Service for Apache Airflow is too expensive for this use case. The small Managed Service for Apache Airflow 2 environment fee alone is $0.35/hour, before compute, memory, storage, and logs.

## AWS Comparison

| Option | Shape | Estimate | Assessment |
| --- | --- | ---: | --- |
| Lightsail 4 GiB instance | Docker Compose monolith on one VPS | About $25-$28/mo with snapshots, depending on stored snapshot data | Lowest sticker-price competitor. Worth considering only if moving the platform to AWS has value beyond cost. |
| EC2 `t4g.medium` | Compose on EC2 with gp3 EBS and public IPv4 | About $35-$39/mo before heavy bandwidth | More AWS-native control, more moving parts, not cheaper. |
| Lightsail Containers | Managed container service | $80/mo for one 2 vCPU / 4 GiB node | Too expensive for the current monolith and still needs persistent data strategy. |
| ECS Fargate | Serverless containers | $100+/mo once ALB/RDS/EFS/logs are included | Operationally solid, but not monolithic or low-cost. |
| App Runner/Lambda hybrid | Web services on App Runner, jobs on Lambda | Variable, likely $50-$150+/mo with database | Good cloud-native pattern, but it redesigns the platform. |
| MWAA | Managed Airflow | $449/mo in AWS small-environment example | Not cost-effective. |

## Google Cloud Comparison

| Option | Shape | Estimate | Assessment |
| --- | --- | ---: | --- |
| Compute Engine `e2-medium` | Docker Compose monolith on one VM | About $37-$41/mo with balanced disk, external IPv4, and snapshots | Works, but costs more than DigitalOcean/Lightsail for the same monolithic shape. |
| Cloud Run + Cloud SQL + Cloud Composer | Serverless web/job pieces plus managed Airflow | $300+/mo once Composer is included | Serverless for web, not cost-effective for Airflow. |
| Cloud Run only | DotDev and selected jobs | Low to near-free for light traffic | Requires dropping or redesigning Airflow and Prefect Server. |
| GKE Autopilot | Kubernetes-managed containers | Higher than a VPS for this workload | Too much platform for a personal monolith. |

## Cost Ranking

| Rank | Provider/option | Approximate monthly cost | Monolithic fit | Recommendation |
| ---: | --- | ---: | --- | --- |
| 1 | DigitalOcean 2 GiB Droplet | $14.40 | Strong | Current production shape. |
| 2 | AWS Lightsail 4 GiB VPS | $25-$28 | Strong | Cost competitor, but migration effort is not worth it unless standardizing on AWS has separate value. |
| 3 | DigitalOcean 4 GiB Droplet | $28.80 | Strong | Safe fallback if the 2 GiB host is too tight. |
| 4 | Google Compute Engine `e2-medium` | $37-$41 | Strong | Viable but not cheaper. |
| 5 | DigitalOcean two-Droplet split | $43.20 | Medium | Use only if Airflow isolation becomes necessary. |
| 6 | DigitalOcean App Platform plus Airflow Droplet | $60.80-$68.80+ | Medium | More managed, more expensive, less monolithic. |
| 7 | AWS/GCP managed Airflow paths | $300-$450+ | Weak | Reject for cost. |

## Decision

Proceed with the existing DigitalOcean single-Droplet deployment unless monitoring proves that Airflow needs isolation or more memory. The most cost-effective architecture that still behaves like a monolith is one VPS with Docker Compose. Serverless should be treated as a later optimization for individual jobs, not as the core deployment target.

## Sources

- [DigitalOcean Droplet pricing](https://www.digitalocean.com/pricing/droplets)
- [DigitalOcean backups pricing](https://docs.digitalocean.com/products/backups/details/pricing/)
- [DigitalOcean App Platform pricing](https://docs.digitalocean.com/products/app-platform/details/pricing/)
- [DigitalOcean App Platform storage limits](https://docs.digitalocean.com/products/app-platform/how-to/store-data/)
- [DigitalOcean Functions pricing](https://docs.digitalocean.com/products/functions/details/pricing/)
- [DigitalOcean Functions limits](https://docs.digitalocean.com/products/functions/details/limits/)
- [Amazon Lightsail instance bundles](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html)
- [Amazon Lightsail container pricing](https://aws.amazon.com/lightsail/pricing/?c=containers&p=ft&z=3)
- [AWS App Runner pricing](https://aws.amazon.com/apprunner/pricing/)
- [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/)
- [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/)
- [Amazon EventBridge pricing](https://aws.amazon.com/eventbridge/pricing/)
- [Amazon MWAA pricing](https://aws.amazon.com/managed-workflows-for-apache-airflow/pricing/)
- [Google Cloud Run pricing](https://cloud.google.com/run/pricing)
- [Google Compute Engine VM pricing](https://cloud.google.com/compute/vm-instance-pricing)
- [Google Compute Engine disk pricing](https://cloud.google.com/compute/disks-image-pricing)
- [Google VPC network pricing](https://cloud.google.com/vpc/network-pricing)
- [Google Cloud SQL pricing](https://cloud.google.com/sql/pricing)
- [Google Managed Service for Apache Airflow pricing](https://cloud.google.com/composer/pricing)
