# Complete Airflow Deployment Guide

This comprehensive guide covers the entire setup process for deploying Apache Airflow to Digital Ocean with automated CI/CD via GitHub Actions.

---

## Table of Contents

1. [Digital Ocean Account Setup](#1-digital-ocean-account-setup)
2. [GitHub Repository Setup](#2-github-repository-setup)
3. [DNS Configuration (Squarespace)](#3-dns-configuration-squarespace)
4. [First Deployment](#4-first-deployment)
5. [Local Development](#5-local-development)
6. [Troubleshooting](#6-troubleshooting)
7. [Maintenance](#7-maintenance)

---

## 1. Digital Ocean Account Setup

### Overview

You'll need a Digital Ocean account with:
- API token for Terraform automation
- SSH key for secure Droplet access
- Spaces bucket for Terraform state storage
- Sufficient credit/payment method for infrastructure costs

**Estimated monthly cost**: $6-11 (Droplet + Spaces for Terraform state)

### 1.1 Create Digital Ocean Account

1. **Sign up** at https://www.digitalocean.com/
2. **Verify email** and complete profile
3. **Add payment method** in Account → Billing
4. **Optional**: Apply promo code for $200 credit

### 1.2 Generate API Token

1. Go to **API** → https://cloud.digitalocean.com/account/api/tokens
2. Click **Generate New Token**
3. Configure:
   - **Name**: `airflow-terraform`
   - **Expiration**: 90 days (recommended)
   - **Scopes**: Write (read and write access)
4. **Copy the token immediately** - you won't see it again
5. Store securely - this becomes `DO_TOKEN` in GitHub Secrets

### 1.3 Generate SSH Key Pair

```bash
# Generate ED25519 key (recommended)
ssh-keygen -t ed25519 -C "airflow-deployment" -f ~/.ssh/airflow_deploy

# Press Enter twice (no passphrase for CI/CD)
```

This creates:
- `~/.ssh/airflow_deploy` - Private key (add to GitHub Secrets)
- `~/.ssh/airflow_deploy.pub` - Public key (add to Digital Ocean)

### 1.4 Add SSH Key to Digital Ocean

1. Copy public key: `cat ~/.ssh/airflow_deploy.pub`
2. Go to https://cloud.digitalocean.com/account/security
3. Click **Add SSH Key**, paste the public key
4. Name: `airflow-deployment`
5. Click **Add SSH Key**

### 1.5 Get SSH Key Fingerprint

**From Digital Ocean Dashboard**:
- Find your key in Security settings
- Copy the **Fingerprint** value (looks like `ab:cd:ef:12:34:...`)

**Or calculate locally**:
```bash
ssh-keygen -l -E md5 -f ~/.ssh/airflow_deploy.pub | awk '{print $2}' | sed 's/MD5://'
```

### 1.6 Set Up Spaces for Terraform State

**Cost**: $5/month

1. Go to https://cloud.digitalocean.com/spaces
2. Click **Create a Space**
3. Configure:
   - **Region**: `sfo3` (must match `terraform/backend.tf`)
   - **Name**: `airflow-terraform-state`
4. Click **Create Space**

> **Note**: If you use a different region, update `terraform/backend.tf` endpoint to match (e.g., `https://nyc3.digitaloceanspaces.com`)

### 1.7 Generate Spaces Access Keys

1. Go to **API** → **Spaces Keys** → https://cloud.digitalocean.com/account/api/spaces
2. Click **Generate New Key**
3. Name: `airflow-terraform`
4. **Copy both keys immediately**:
   - Access Key → `SPACES_ACCESS_KEY_ID`
   - Secret Key → `SPACES_SECRET_ACCESS_KEY`

### Cost Breakdown

| Resource | Cost |
|----------|------|
| Droplet (s-1vcpu-1gb) | $6/month |
| Spaces | $5/month |
| **Total** | $11/month |

---

## 2. GitHub Repository Setup

### Required GitHub Secrets

| Secret Name | Purpose |
|-------------|---------|
| `DO_TOKEN` | Digital Ocean API authentication |
| `DO_SSH_PRIVATE_KEY` | SSH access to Droplet |
| `DO_SSH_KEY_FINGERPRINT` | Identify SSH key in Digital Ocean |
| `SPACES_ACCESS_KEY_ID` | Terraform state storage |
| `SPACES_SECRET_ACCESS_KEY` | Terraform state storage |
| `AIRFLOW_ADMIN_USER` | Airflow admin username |
| `AIRFLOW_ADMIN_PASSWORD` | Airflow admin password |
| `AIRFLOW_FERNET_KEY` | Encryption key for Airflow secrets |
| `AIRFLOW_WEBSERVER_SECRET_KEY` | Flask session secret |
| `POSTGRES_PASSWORD` | PostgreSQL database password |

### 2.1 Create GitHub Repository

**Option A: Using GitHub CLI**
```bash
# Login to GitHub
gh auth login

# Create repository (from project directory)
gh repo create airflow-digitalocean --private --source=. --remote=origin

# Push code
git add .
git commit -m "Initial commit"
git push -u origin main
```

**Option B: Using GitHub Web**
1. Go to https://github.com/new
2. Repository name: `airflow-digitalocean`
3. Select **Private**
4. Click **Create repository**
5. Follow the "push an existing repository" instructions

### 2.2 Add DO_TOKEN

1. Copy your Digital Ocean API token
2. Go to GitHub repo → **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `DO_TOKEN`, Value: your token

### 2.3 Add DO_SSH_PRIVATE_KEY

```bash
cat ~/.ssh/airflow_deploy
```

Copy the **entire output** including `-----BEGIN/END OPENSSH PRIVATE KEY-----` lines.

Add as secret `DO_SSH_PRIVATE_KEY`.

### 2.4 Add DO_SSH_KEY_FINGERPRINT

Copy the fingerprint from Digital Ocean (format: `ab:cd:ef:12:34:56:78:90:...`).

Add as secret `DO_SSH_KEY_FINGERPRINT`.

### 2.5 Add Spaces Credentials

- `SPACES_ACCESS_KEY_ID`: Access key from Spaces
- `SPACES_SECRET_ACCESS_KEY`: Secret key from Spaces

### 2.6 Generate Airflow Secrets

```bash
# Generate Fernet key
python scripts/generate-fernet-key.py
# Copy the key output

# Generate webserver secret
python -c "import secrets; print(secrets.token_hex(32))"
# Copy the output

# Generate admin password
python -c "import secrets; print(secrets.token_urlsafe(16))"
# Copy the output

# Generate Postgres password
python -c "import secrets; print(secrets.token_urlsafe(16))"
# Copy the output
```

Add secrets:
- `AIRFLOW_ADMIN_USER`: `admin` (or your choice)
- `AIRFLOW_ADMIN_PASSWORD`: Generated password
- `AIRFLOW_FERNET_KEY`: Generated Fernet key
- `AIRFLOW_WEBSERVER_SECRET_KEY`: Generated secret
- `POSTGRES_PASSWORD`: Generated password

### Verification Checklist

- [ ] All 10 secrets added to GitHub
- [ ] `DO_TOKEN` has write access
- [ ] SSH public key added to Digital Ocean
- [ ] `DO_SSH_KEY_FINGERPRINT` matches Digital Ocean
- [ ] Passwords are strong (16+ characters)
- [ ] Spaces bucket exists with correct name

---

## 3. DNS Configuration (Squarespace)

### Overview

After Terraform provisions your Droplet, configure DNS so `flow.raniendu.dev` points to the Droplet's IP address.

### 3.1 Get Droplet IP Address

**From GitHub Actions**:
1. Go to **Actions** tab
2. Click recent workflow run
3. Check the **Deployment Summary** job
4. Find the Droplet IP in the summary

**From Digital Ocean**:
1. Go to https://cloud.digitalocean.com/droplets
2. Find `airflow-server` Droplet
3. Copy IPv4 address

### 3.2 Add A Record in Squarespace

1. Log in to https://account.squarespace.com/
2. Go to **Settings** → **Domains** → your domain → **DNS Settings**
3. Click **Add Record**
4. Configure:

| Field | Value |
|-------|-------|
| Type | `A` |
| Host | `flow` |
| Data | Your Droplet IP |
| TTL | `3600` (or default) |

5. Click **Save**

### 3.3 Wait for DNS Propagation

- **Typical time**: 5-30 minutes
- **Maximum**: 48 hours (rare)

### 3.4 Test DNS Resolution

```bash
# Using dig
dig flow.raniendu.dev

# Using nslookup
nslookup flow.raniendu.dev

# Using ping
ping flow.raniendu.dev
```

Should return your Droplet IP.

### 3.5 Clear DNS Cache (if needed)

```bash
# macOS
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
```

---

## 4. First Deployment

### 4.1 Pre-Deployment Checklist

- [ ] Digital Ocean account configured (Section 1)
- [ ] All GitHub Secrets added (Section 2)
- [ ] Repository pushed to GitHub
- [ ] On `main` branch

### 4.2 Trigger Deployment

```bash
git checkout main
git add .
git commit -m "Initial Airflow deployment"
git push origin main
```

### 4.3 Monitor GitHub Actions

1. Go to **Actions** tab
2. Watch workflow progress:
   - **Provision Infrastructure**: ~3-5 minutes
   - **Deploy Application**: ~5-10 minutes
   - **Deployment Summary**: Shows next steps

### 4.4 Configure DNS

After Terraform completes:
1. Get Droplet IP from workflow summary
2. Add A record in Squarespace (see Section 3)
3. Wait for DNS propagation

### 4.5 Wait for SSL Certificate

The workflow automatically handles SSL certificates. If DNS wasn't ready on first deploy:
1. Wait for DNS to propagate
2. Re-run the workflow: **Actions** → Click workflow → **Re-run all jobs**

### 4.6 Access Airflow UI

1. Open https://flow.raniendu.dev
2. Log in with:
   - Username: Your `AIRFLOW_ADMIN_USER`
   - Password: Your `AIRFLOW_ADMIN_PASSWORD`
3. Verify dashboard loads and `example_dag` is visible

### 4.7 Post-Deployment Verification

```bash
# SSH to Droplet
ssh -i ~/.ssh/airflow_deploy root@<droplet-ip>

# Check all containers
docker ps
# Should show: airflow_webserver, airflow_scheduler, airflow_postgres, airflow_nginx, airflow_certbot

# Check Airflow health
curl -sf http://localhost:8080/health

# View logs
cd /opt/airflow
docker compose logs -f
```

### 4.8 Run Test DAG

1. In Airflow UI, find `example_dag`
2. Toggle it to **Active** (switch on left)
3. Click **Play** button → **Trigger DAG**
4. Verify DAG completes successfully (green)

---

## 5. Local Development

### 5.1 Prerequisites (macOS)

```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Docker Desktop
brew install --cask docker

# Install UV (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Launch Docker Desktop
open -a Docker
```

### 5.2 Install Dependencies

```bash
uv sync
```

### 5.3 Start Local Airflow

```bash
# Start all services (first run takes 2-5 minutes)
docker compose -f docker-compose.local.yml up

# Or run in background
docker compose -f docker-compose.local.yml up -d
```

### 5.4 Access Local Airflow

1. Open http://localhost:8080
2. Login with any username (e.g., `admin`) — no password needed
3. DAGs in `dags/` directory are automatically loaded

### 5.5 Validate DAGs

```bash
python scripts/validate-dags.py
```

### 5.6 Stop Local Environment

```bash
# Stop containers
docker compose -f docker-compose.local.yml down

# Stop and remove volumes (reset database)
docker compose -f docker-compose.local.yml down -v
```

### Local vs Production

| Component | Local | Production |
|-----------|-------|------------|
| Executor | SequentialExecutor | LocalExecutor |
| Database | SQLite | PostgreSQL |
| Authentication | Disabled | Password-based |
| SSL | None | Let's Encrypt |

---

## 6. Troubleshooting

### Terraform Errors

| Error | Solution |
|-------|----------|
| Invalid API token | Verify `DO_TOKEN` secret |
| SSH key not found | Check `DO_SSH_KEY_FINGERPRINT` |
| Backend init failed | Verify Spaces credentials and bucket exists |
| Resource quota exceeded | Check Digital Ocean limits |

### SSH Connection Failed

- Verify `DO_SSH_PRIVATE_KEY` includes BEGIN/END lines
- Check fingerprint matches Digital Ocean
- Ensure public key is added to Digital Ocean

### DNS Not Resolving

- Wait longer (up to 48 hours)
- Verify A record is saved in Squarespace
- Clear local DNS cache
- Try: `dig @8.8.8.8 flow.raniendu.dev`

### SSL Certificate Not Working

- Ensure DNS is working first
- Wait 10-15 minutes after DNS propagation
- Re-run GitHub Actions workflow
- Check Certbot logs:
  ```bash
  ssh root@<droplet-ip>
  cd /opt/airflow
  docker compose logs certbot
  ```

### Can't Log In to Airflow UI

- Verify username/password match GitHub Secrets
- Check for special characters in password
- Redeploy to regenerate credentials

### DAGs Not Appearing

```bash
# SSH to Droplet
ssh root@<droplet-ip>
cd /opt/airflow

# Reserialize DAGs
docker exec airflow_webserver airflow dags reserialize

# Check scheduler logs
docker compose logs airflow-scheduler
```

### Container Issues

```bash
# SSH to Droplet
ssh root@<droplet-ip>
cd /opt/airflow

# View all logs
docker compose logs -f

# Restart all services
docker compose restart

# Full restart
docker compose down
docker compose up -d
```

### GitHub Actions Failed

1. Check **Actions** tab for error details
2. Verify all 10 secrets are set correctly
3. Ensure `DO_SSH_PRIVATE_KEY` includes BEGIN/END lines
4. Check Droplet is running in DO dashboard
5. Re-run failed jobs if transient error

---

## 7. Maintenance

### Common Commands

```bash
# SSH to Droplet
ssh -i ~/.ssh/airflow_deploy root@<droplet-ip>

# View logs
docker compose logs -f [service]

# Restart services
docker compose restart

# Update deployment (push to main triggers CI/CD)
git push origin main
```

### Temporarily Pause Deployment (Cost Saving)

Use the Terraform infra toggle to remove active Airflow infrastructure while keeping all code and state for later reactivation.

Pause steps:

```bash
cd terraform
# Ensure this file contains: infra_enabled = false
cat deployment.auto.tfvars

terraform plan
terraform apply
```

Resume steps:

```bash
cd terraform
# Change deployment.auto.tfvars to: infra_enabled = true
terraform plan
terraform apply
```

When using GitHub Actions:

1. Commit and push `terraform/deployment.auto.tfvars` with `infra_enabled=false` to pause.
2. Terraform apply destroys managed Airflow infra.
3. Deploy job is skipped automatically while paused.
4. Set `infra_enabled=true` and push to recreate infra and resume deploys.

### Pause/Resume Verification Checklist

After pause (`infra_enabled=false`):

- [ ] `terraform plan` shows destroy/no-op for managed Airflow resources only
- [ ] `airflow-server` droplet no longer exists
- [ ] unrelated resources (for example `prefect-server`, App Platform apps) remain unchanged
- [ ] workflow summary reports infrastructure paused

After resume (`infra_enabled=true`):

- [ ] `terraform plan` shows create/update for Airflow-managed resources
- [ ] new Airflow droplet IP is produced
- [ ] deploy job runs in CI/CD
- [ ] Airflow UI becomes reachable again after deployment

### Regular Tasks

**Weekly**:
- Check DAG run success rates in Airflow UI
- Review error logs
- Monitor resource usage

**Monthly**:
- Update Docker images (push to main)
- Review costs in DO dashboard
- Check SSL certificate expiration

**Quarterly**:
- Rotate API tokens and passwords
- Update dependencies in `pyproject.toml`
- Test disaster recovery

### Security Recommendations

- [ ] Enable 2FA on Digital Ocean and GitHub
- [ ] Set up billing alerts in DO
- [ ] Rotate credentials every 90 days
- [ ] Review firewall rules: `ufw status`

---

## Success Checklist

- [ ] GitHub Actions workflow completed
- [ ] Droplet running in Digital Ocean
- [ ] DNS resolves to Droplet IP
- [ ] HTTPS works without warnings
- [ ] Can log in to Airflow UI
- [ ] Scheduler is running
- [ ] Example DAG runs successfully

**Congratulations! Your Airflow deployment is complete! 🎉**

---

## Quick Reference

### GitHub Secrets Summary

| Secret | Source |
|--------|--------|
| `DO_TOKEN` | DO → API → Tokens |
| `DO_SSH_KEY_FINGERPRINT` | DO → Settings → Security → SSH Keys |
| `DO_SSH_PRIVATE_KEY` | `cat ~/.ssh/airflow_deploy` |
| `SPACES_ACCESS_KEY_ID` | DO → API → Spaces Keys |
| `SPACES_SECRET_ACCESS_KEY` | DO → API → Spaces Keys |
| `AIRFLOW_ADMIN_USER` | Your choice (e.g., `admin`) |
| `AIRFLOW_ADMIN_PASSWORD` | Generated password |
| `AIRFLOW_FERNET_KEY` | `python scripts/generate-fernet-key.py` |
| `AIRFLOW_WEBSERVER_SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `POSTGRES_PASSWORD` | Generated password |

### URLs

| Environment | URL |
|-------------|-----|
| Local | http://localhost:8080 |
| Production | https://flow.raniendu.dev |
| GitHub Actions | github.com/YOUR_USER/YOUR_REPO/actions |
| DO Dashboard | cloud.digitalocean.com |
| Squarespace DNS | squarespace.com → Settings → Domains |

---

## Additional Resources

- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [Digital Ocean Documentation](https://docs.digitalocean.com/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Terraform Digital Ocean Provider](https://registry.terraform.io/providers/digitalocean/digitalocean/latest/docs)
