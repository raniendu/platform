# DigitalOcean Cost Comparison

Pricing snapshot: 2026-04-26. Prices are public USD list prices before tax, support, unusual bandwidth, and one-off snapshot storage.

## Live Inventory

Observed with `doctl` on 2026-04-26:

| Resource | State | Size | Role |
| --- | --- | --- | --- |
| Droplet `platform-shared` | active | 2 vCPU, 4 GiB RAM, 80 GiB disk | New consolidated Docker Compose host |
| Firewall `platform-shared-firewall` | active | SSH from one admin `/32`, HTTP/HTTPS public | New consolidated firewall |
| Droplet backups for `platform-shared` | active | weekly backup plan | Backup cost included in consolidated estimate |
| Droplet `prefect-server` | active | 1 vCPU, 1 GiB RAM, 25 GiB disk | Old Prefect host |
| App Platform `dot-dev-app` | active | `apps-s-1vcpu-0.5gb`, 1 instance | Old DotDev app |
| Managed databases | none | n/a | No active DO managed DB cost |
| Volumes | none | n/a | No active block storage volume cost |
| Load balancers | none | n/a | No active load balancer cost |
| Snapshots | none listed | n/a | No old standalone snapshot cost observed |

The old Airflow Terraform defaults describe an `s-1vcpu-1gb` Droplet named `airflow-server`, but `infra_enabled` defaults to `false` and no active Airflow Droplet was visible in the DigitalOcean inventory.

## Cost Estimate

| Scenario | Components | Estimated monthly cost |
| --- | --- | ---: |
| Current consolidated platform only | `platform-shared` Basic Droplet at $24.00 plus weekly backups at 20% | $28.80 |
| Still-overlapped current state | Consolidated platform plus old `prefect-server` plus old `dot-dev-app` | $39.80 |
| Visible old infra only | Old Prefect Droplet plus old DotDev App Platform app | $11.00 |
| Historical old infra if Airflow were enabled | Old Prefect Droplet, old DotDev App Platform app, old Airflow 1 GiB Droplet | $17.00 |

## Interpretation

The consolidated Droplet is not cheaper than the currently visible old Prefect and DotDev resources by raw monthly list price. It is the cheaper option for the chosen operating model: one monorepo, one Docker Compose runtime, one deployment path, one firewall, Caddy-managed HTTPS, local Postgres containers, and enough memory for Airflow to run continuously.

The immediate cost risk is overlap. Keeping the old Prefect Droplet and old DotDev App Platform app live after cutover adds about $11.00/month. If the old Airflow Droplet is re-enabled, overlap rises to about $17.00/month.

After deprecating old resources, the steady-state DigitalOcean bill for this platform should be about $28.80/month at current list prices. Without backups it would be $24.00/month, but backups are intentionally enabled for rollback.

## Cost Notes

- DigitalOcean bills Droplets while powered off because compute capacity remains reserved. Destroying, not powering off, is required to stop Droplet charges.
- Weekly percentage backups add 20% of the Droplet cost.
- The old `dot-dev-app` App Platform service is a dynamic web service, not a static-site free tier app.
- No managed database, volume, or load balancer costs were observed.

## Sources

- [DigitalOcean Droplet pricing](https://www.digitalocean.com/pricing/droplets)
- [DigitalOcean Droplet billing notes](https://docs.digitalocean.com/products/droplets/details/pricing/)
- [DigitalOcean backups pricing](https://docs.digitalocean.com/products/backups/details/pricing/)
- [DigitalOcean App Platform pricing](https://docs.digitalocean.com/products/app-platform/details/pricing/)
