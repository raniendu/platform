# Platform Documentation

Use this directory as the operational map for the platform monorepo. The root
`README.md` is the quick start; this index points to the deeper runbooks.

## Start Here

| Need | Read |
| --- | --- |
| Understand the system shape | [Architecture](architecture.md) |
| Set up local development | [Local development](local-development.md) |
| Work on one app | [Developer guide](developer-guide.md) |
| Deploy or review deploy behavior | [Deployment](deployment.md) |
| Operate production | [Operations](operations.md) |
| Manage secrets | [Secrets](secrets.md) |
| Roll back a bad deploy | [Rollback](rollback.md) |

## App References

App-specific architecture notes live under [apps/](apps/README.md). Use those
when changing code inside one app, and use the shared docs here when changing
Compose, Caddy, Terraform, GitHub Actions, DNS, secrets, or production flags.

## Infrastructure And Cost

- [Cloud architecture recommendation](cloud-architecture-recommendation.md)
- [DigitalOcean cost comparison](digitalocean-cost-comparison.md)
- [DigitalOcean cost optimization plan](digitalocean-cost-optimization-plan.md)
- [DNS cutover](dns-cutover.md)
- [Smaller Droplet migration](smaller-droplet-migration.md)
- [Deprecation plan](deprecation-plan.md)

## Data

- [Database ownership](database/README.md)
- [PyDBML datastore model](database/platform-app-datastores.dbml)

Keep documentation changes close to behavior changes. Deployment, DNS, secret,
Terraform, app flag, or operations changes should update the matching runbook in
this directory before the PR is opened.
