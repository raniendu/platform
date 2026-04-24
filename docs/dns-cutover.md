# DNS Cutover

Squarespace remains the manual DNS control point.

Do not change DNS until:

- local verification passes,
- the GitHub repo exists,
- production secrets are configured,
- Terraform apply is approved and complete,
- the new Droplet is running the production Compose stack.

## Records To Update

Use the Terraform output `droplet_ip` as the A record value.

- `raniendu.dev` -> new Droplet IP
- `prefect.raniendu.dev` -> new Droplet IP
- `flow.raniendu.dev` -> new Droplet IP

If Squarespace uses host labels:

- root/apex: `@`
- Prefect: `prefect`
- Airflow: `flow`

## After Saving

Wait for DNS propagation, then verify:

```bash
dig +short raniendu.dev
dig +short prefect.raniendu.dev
dig +short flow.raniendu.dev
curl -I https://raniendu.dev/
curl -I https://prefect.raniendu.dev/
curl -I https://flow.raniendu.dev/
```

Keep old services live until all public endpoints are verified.

