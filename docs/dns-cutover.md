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
- `www.raniendu.dev` -> CNAME to `raniendu.dev`
- `prefect.raniendu.dev` -> new Droplet IP
- `flow.raniendu.dev` -> new Droplet IP

If Squarespace uses host labels:

- root/apex: `@`
- www: `www`
- Prefect: `prefect`
- Airflow: `flow`

Expected Squarespace record shape:

```text
A      @        174.138.59.96
CNAME  www      raniendu.dev
A      prefect  174.138.59.96
A      flow     174.138.59.96
```

Do not use an `ALIAS` record when the target is an IP address. The root/apex record must be type `A`.

## After Saving

Wait for DNS propagation, then verify:

```bash
dig +short raniendu.dev
dig +short www.raniendu.dev
dig +short prefect.raniendu.dev
dig +short flow.raniendu.dev
curl -I https://raniendu.dev/
curl -I https://www.raniendu.dev/
curl -I https://prefect.raniendu.dev/
curl -I https://flow.raniendu.dev/
```

Keep old services live until all public endpoints are verified.
