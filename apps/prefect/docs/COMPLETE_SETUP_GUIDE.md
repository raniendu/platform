# Complete Prefect Deployment Guide

This comprehensive guide covers the entire setup process for deploying Prefect to Digital Ocean with automated CI/CD via GitHub Actions.

---

## Table of Contents

1. [Digital Ocean Account Setup](#1-digital-ocean-account-setup)
2. [GitHub Repository Setup](#2-github-repository-setup)
3. [DNS Configuration](#3-dns-configuration)
4. [First Deployment](#4-first-deployment)
5. [Troubleshooting](#5-troubleshooting)
6. [Maintenance](#6-maintenance)

---

## 1. Digital Ocean Account Setup

### Overview

You'll need a Digital Ocean account with:
- API token for Terraform automation
- SSH key for secure Droplet access
- Sufficient credit/payment method for infrastructure costs

**Estimated monthly cost**: $6-11 (Droplet + optional Spaces for Terraform state)

### 1.1 Create Digital Ocean Account

1. **Sign up** at https://www.digitalocean.com/
2. **Verify email** and complete profile
3. **Add payment method** in Account → Billing
4. **Optional**: Apply promo code for $200 credit

### 1.2 Generate API Token

1. Go to **API** → https://cloud.digitalocean.com/account/api/tokens
2. Click **Generate New Token**
3. Configure:
   - **Name**: `prefect-terraform`
   - **Expiration**: 90 days (recommended)
   - **Scopes**: Write (read and write access)
4. **Copy the token immediately** - you won't see it again
5. Store securely - this becomes `DO_TOKEN` in GitHub Secrets

### 1.3 Generate SSH Key Pair

```bash
# Generate ED25519 key (recommended)
ssh-keygen -t ed25519 -C "prefect-deployment" -f ~/.ssh/prefect_deploy

# Or RSA key
ssh-keygen -t rsa -b 4096 -C "prefect-deployment" -f ~/.ssh/prefect_deploy
```

This creates:
- `~/.ssh/prefect_deploy` - Private key (add to GitHub Secrets)
- `~/.ssh/prefect_deploy.pub` - Public key (add to Digital Ocean)

### 1.4 Add SSH Key to Digital Ocean

1. Copy public key: `cat ~/.ssh/prefect_deploy.pub`
2. Go to https://cloud.digitalocean.com/account/security
3. Click **Add SSH Key**, paste the public key
4. Name: `prefect-deployment`

### 1.5 Get SSH Key Fingerprint

**From Digital Ocean Dashboard**:
- Find your key in Security settings
- Copy the **Fingerprint** value

**Or calculate locally**:
```bash
ssh-keygen -l -E md5 -f ~/.ssh/prefect_deploy.pub | awk '{print $2}' | sed 's/MD5://'
```

### 1.6 Optional: Set Up Spaces for Terraform State

**Cost**: $5/month

1. Go to https://cloud.digitalocean.com/spaces
2. Create Space named `prefect-terraform-state`
3. Generate Spaces access keys in **API** → **Spaces Keys**
4. Save Access Key and Secret Key for GitHub Secrets

### Cost Breakdown

| Resource | Cost |
|----------|------|
| Droplet (s-1vcpu-1gb) | $6/month |
| Spaces (optional) | $5/month |
| **Total** | $6-11/month |

---

## 2. GitHub Repository Setup

### Required GitHub Secrets

| Secret Name | Purpose |
|-------------|---------|
| `DO_TOKEN` | Digital Ocean API authentication |
| `DO_SSH_PRIVATE_KEY` | SSH access to Droplet |
| `DO_SSH_KEY_FINGERPRINT` | Identify SSH key in Digital Ocean |
| `PREFECT_AUTH_USERNAME` | Basic auth username for Prefect UI |
| `PREFECT_AUTH_PASSWORD` | Basic auth password for Prefect UI |
| `POSTGRES_PASSWORD` | PostgreSQL database password |
| `PUSHOVER_APP_TOKEN` | Pushover application API token for notifications |
| `PUSHOVER_USER_KEY` | Pushover user key for notifications |
| `SPACES_ACCESS_KEY_ID` | (Optional) Terraform state storage |
| `SPACES_SECRET_ACCESS_KEY` | (Optional) Terraform state storage |

### 2.1 Add DO_TOKEN

1. Copy your Digital Ocean API token
2. Go to GitHub repo → **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `DO_TOKEN`, Value: your token

### 2.2 Add DO_SSH_PRIVATE_KEY

```bash
cat ~/.ssh/prefect_deploy
```

Copy the entire output including `-----BEGIN/END OPENSSH PRIVATE KEY-----` lines.

Add as secret `DO_SSH_PRIVATE_KEY`.

### 2.3 Add DO_SSH_KEY_FINGERPRINT

Copy the fingerprint from Digital Ocean (without `MD5:` prefix).

Add as secret `DO_SSH_KEY_FINGERPRINT`.

### 2.4 Set Authentication Credentials

Generate strong passwords:
```bash
openssl rand -base64 32
```

Add secrets:
- `PREFECT_AUTH_USERNAME`: Your chosen username
- `PREFECT_AUTH_PASSWORD`: Generated password
- `POSTGRES_PASSWORD`: Generated password
- `PUSHOVER_APP_TOKEN`: Your Pushover application API token
- `PUSHOVER_USER_KEY`: Your Pushover user key

### 2.5 Optional: Spaces Credentials

If using Digital Ocean Spaces for Terraform state:
- `SPACES_ACCESS_KEY_ID`: Access key from Spaces
- `SPACES_SECRET_ACCESS_KEY`: Secret key from Spaces

### Verification Checklist

- [ ] All required secrets added to GitHub
- [ ] `DO_TOKEN` has write access
- [ ] SSH public key added to Digital Ocean
- [ ] `DO_SSH_KEY_FINGERPRINT` matches Digital Ocean
- [ ] Passwords are strong (20+ characters)

---

## 3. DNS Configuration

### Overview

After Terraform provisions your Droplet, configure DNS so `prefect.raniendu.dev` points to the Droplet's IP address.

### 3.1 Get Droplet IP Address

**From GitHub Actions**:
1. Go to **Actions** tab
2. Click recent workflow run
3. Expand **Terraform Apply** step
4. Find: `droplet_ip = "164.90.XXX.XXX"`

**From Digital Ocean**:
1. Go to https://cloud.digitalocean.com/droplets
2. Find `prefect-server` Droplet
3. Copy IPv4 address

### 3.2 Add A Record in Squarespace

1. Log in to https://account.squarespace.com/
2. Go to **Settings** → **Domains** → `raniendu.dev` → **DNS Settings**
3. Add new A record:

| Field | Value |
|-------|-------|
| Host | `prefect` |
| Type | `A` |
| Points To | Your Droplet IP |
| TTL | `3600` |

4. Save the record

### 3.3 Wait for DNS Propagation

- **Typical time**: 5-30 minutes
- **Maximum**: 48 hours (rare)

### 3.4 Test DNS Resolution

```bash
# Using dig
dig prefect.raniendu.dev

# Using nslookup
nslookup prefect.raniendu.dev

# Using ping
ping prefect.raniendu.dev
```

Should return your Droplet IP.

### 3.5 Clear DNS Cache (if needed)

```bash
# macOS
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder

# Linux
sudo systemd-resolve --flush-caches

# Windows
ipconfig /flushdns
```

---

## 4. First Deployment

### 4.1 Pre-Deployment Checklist

- [ ] Digital Ocean account configured
- [ ] All GitHub Secrets added
- [ ] Repository cloned locally
- [ ] On `main` branch with no uncommitted changes

### 4.2 Trigger Deployment

```bash
git checkout main
git commit --allow-empty -m "Initial Prefect deployment"
git push origin main
```

### 4.3 Monitor GitHub Actions

1. Go to **Actions** tab
2. Watch workflow progress:
   - **Terraform Apply**: ~3-5 minutes
   - **Deploy to Droplet**: ~5-10 minutes
   - **Deploy Flows**: ~1-2 minutes

### 4.4 Configure DNS

After Terraform completes:
1. Get Droplet IP from workflow output
2. Add A record in Squarespace (see Section 3)
3. Wait for DNS propagation

### 4.5 Wait for SSL Certificate

After DNS propagates:
1. Wait 5-10 minutes for Let's Encrypt
2. Check certificate status:
   ```bash
   ssh root@prefect.raniendu.dev
   cd /opt/prefect
   docker compose -f docker-compose.prod.yml logs certbot
   ```

### 4.6 Access Prefect UI

1. Open https://prefect.raniendu.dev
2. Log in with `PREFECT_AUTH_USERNAME` and `PREFECT_AUTH_PASSWORD`
3. Verify dashboard loads

### 4.7 Post-Deployment Verification

```bash
# SSH to Droplet
ssh root@prefect.raniendu.dev

# Check all containers
docker ps
# Should show: nginx, prefect-server, prefect-worker, postgres, certbot

# Check Prefect health
docker run --rm --network prefect-internal curlimages/curl curl -sf http://prefect-server-prod:4200/api/health
```

### 4.8 Run Test Flow

1. In Prefect UI, go to **Flows**
2. Open any registered flow
3. Click **Quick Run**
4. Verify the flow completes successfully

---

## 5. Troubleshooting

### Terraform Errors

| Error | Solution |
|-------|----------|
| Invalid API token | Verify `DO_TOKEN` secret |
| SSH key not found | Check `DO_SSH_KEY_FINGERPRINT` |
| Resource quota exceeded | Check Digital Ocean limits |

### SSH Connection Failed

- Verify `DO_SSH_PRIVATE_KEY` includes BEGIN/END lines
- Check fingerprint matches Digital Ocean
- Ensure public key is added to Digital Ocean

### DNS Not Resolving

- Wait longer (up to 48 hours)
- Verify A record is saved
- Clear local DNS cache
- Try: `dig @8.8.8.8 prefect.raniendu.dev`

### SSL Certificate Not Working

- Ensure DNS is working first
- Wait 10-15 minutes after DNS propagation
- Check Certbot logs: `docker compose logs certbot`
- Manually request:
  ```bash
  cd /opt/prefect
  docker compose -f docker-compose.prod.yml run --rm certbot certonly \
    --webroot --webroot-path=/var/www/certbot \
    -d prefect.raniendu.dev
  ```

### Can't Log In to Prefect UI

- Verify username/password match GitHub Secrets
- Check for special characters
- Redeploy to regenerate htpasswd

### Worker Not Running Flows

- Check worker in UI (Work Pools page)
- Verify work pool name matches
- Check logs: `docker compose logs prefect-worker`
- Restart: `docker compose restart prefect-worker`

### Container Issues

```bash
# View all logs
docker compose -f docker-compose.prod.yml logs -f

# Restart all services
docker compose -f docker-compose.prod.yml restart

# Full restart
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

---

## 6. Maintenance

### Common Commands

```bash
# SSH to Droplet
ssh root@prefect.raniendu.dev

# View logs
docker compose -f docker-compose.prod.yml logs -f [service]

# Restart services
docker compose -f docker-compose.prod.yml restart

# Update deployment
git pull
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

### Regular Tasks

**Weekly**:
- Check flow run success rates
- Review error logs
- Monitor resource usage

**Monthly**:
- Update Docker images
- Review costs
- Check SSL certificate expiration

**Quarterly**:
- Rotate API tokens and passwords
- Update dependencies
- Test disaster recovery

### Security Recommendations

- [ ] Enable 2FA on Digital Ocean and GitHub
- [ ] Set up billing alerts
- [ ] Review firewall rules: `ufw status`
- [ ] Rotate credentials every 90 days

---

## Success Checklist

- [x] GitHub Actions workflow completed
- [x] Droplet running in Digital Ocean
- [x] DNS resolves to Droplet IP
- [x] HTTPS works without warnings
- [x] Can log in to Prefect UI
- [x] Worker is connected and healthy
- [x] Example flow runs successfully

**Congratulations! Your Prefect deployment is complete! 🎉**

---

## Additional Resources

- [Prefect Documentation](https://docs.prefect.io/)
- [Digital Ocean Documentation](https://docs.digitalocean.com/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Terraform Digital Ocean Provider](https://registry.terraform.io/providers/digitalocean/digitalocean/latest/docs)
