# DigitalOcean Cost Comparison

Pricing snapshot: 2026-05-02. Prices are public USD list prices before tax, support, unusual bandwidth, prorated partial-month usage, and one-off snapshot storage.

## Current Live Inventory

Observed with read-only `doctl` on 2026-05-02:

| Resource | State | Size | Role |
| --- | --- | --- | --- |
| Droplet `platform-shared` | active | `s-1vcpu-2gb`, 1 vCPU, 2 GiB RAM, 50 GiB disk | Shared Docker Compose host |
| Droplet backups for `platform-shared` | active | weekly backup plan | Backup cost included in estimate |
| Firewall `platform-shared-firewall` | active | HTTP/HTTPS public, SSH restricted | Shared firewall |
| Managed databases | none observed | n/a | No active DO managed DB cost |
| Volumes | none observed | n/a | No active block storage volume cost |
| Load balancers | none observed | n/a | No active load balancer cost |
| App Platform apps | none observed | n/a | Old DotDev app deleted |
| Standalone snapshots | none observed | n/a | No standalone snapshot cost observed |

Current public routes:

- `https://raniendu.dev`
- `https://www.raniendu.dev` -> redirects to `https://raniendu.dev`
- `https://prefect.raniendu.dev`
- `https://paperclip.raniendu.dev`
- `https://raman.raniendu.dev`
- `https://flow.raniendu.dev`

## Current Cost Estimate

| Component | Monthly cost |
| --- | ---: |
| `platform-shared` Basic Droplet, `s-1vcpu-2gb` | $12.00 |
| Weekly Droplet backups, 20% of Droplet cost | $2.40 |
| Firewalls | $0.00 |
| Managed DBs, App Platform apps, volumes, load balancers, snapshots | $0.00 |
| **Estimated steady state** | **$14.40** |

This is the current steady-state estimate for the deployed platform. The May 2026 invoice can still include prorated usage for the old 4 GiB Droplet before it was deleted on 2026-05-02.

## Historical Baselines

| Scenario | Components | Estimated monthly cost |
| --- | --- | ---: |
| Old visible infra before consolidation | Old Prefect 1 GiB Droplet plus old DotDev App Platform app | $11.00 |
| Old infra if old Airflow 1 GiB Droplet had also been enabled | Old Prefect Droplet, old DotDev App Platform app, old Airflow Droplet | $17.00 |
| Consolidated platform before smaller-Droplet migration | `s-2vcpu-4gb` Droplet plus weekly backups | $28.80 |
| Current optimized platform | `s-1vcpu-2gb` Droplet plus weekly backups | $14.40 |

The old `prefect-server` Droplet, old `dot-dev-app` App Platform app, old `prefect-server-firewall`, and retired 4 GiB `platform-shared` Droplet have all been decommissioned.

## Interpretation

The current platform is cheaper than the 4 GiB consolidated host and keeps the desired operating model: one monorepo, one Docker Compose runtime, one deployment workflow, one firewall, Caddy-managed HTTPS, and local Postgres for Prefect, Paperclip, and Airflow metadata.

The current $14.40/month estimate assumes weekly backups remain enabled. Disabling backups would save about $2.40/month, but backups should stay enabled unless rollback and restore requirements change.

## Cost Notes

- DigitalOcean bills Droplets while powered off because compute capacity remains reserved. Destroying, not powering off, is required to stop Droplet charges.
- Weekly percentage backups add 20% of the Droplet cost.
- Firewalls are free.
- No managed database, volume, load balancer, App Platform app, or standalone snapshot costs were observed.
- Raman DigitalOcean Inference API usage is not included in the Droplet estimate.

## Sources

- [DigitalOcean Droplet pricing](https://www.digitalocean.com/pricing/droplets)
- [DigitalOcean Droplet billing notes](https://docs.digitalocean.com/products/droplets/details/pricing/)
- [DigitalOcean backups pricing](https://docs.digitalocean.com/products/backups/details/pricing/)
- [DigitalOcean App Platform pricing](https://docs.digitalocean.com/products/app-platform/details/pricing/)
