# Airflow Digital Ocean Deployment

Apache Airflow deployment infrastructure for Digital Ocean with automated CI/CD via GitHub Actions.

## Features

- 🐳 Docker-based local development with hot-reload
- 🚀 Automated deployment to Digital Ocean via GitHub Actions
- 🔒 SSL/TLS with Let's Encrypt (flow.raniendu.dev)
- 🔐 Password authentication with Fernet encryption
- 📦 UV-based dependency management
- ✅ Automated DAG validation in CI/CD

## Prerequisites

- Python 3.10+
- Docker and Docker Compose
- UV package manager
- Digital Ocean account (for production)
- Domain name configured (flow.raniendu.dev)

## Local Development Setup

### 1. Install UV

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Start Local Airflow

```bash
docker compose -f docker-compose.local.yml up
```

The Airflow webserver will be available at http://localhost:8080

**Login:** Enter any username (e.g., `admin`) - no password required. Local development uses the Simple Auth Manager with all-admins mode enabled.

**Note:** Local development uses SequentialExecutor with SQLite for simplicity. Production uses LocalExecutor with PostgreSQL.

### 4. Develop DAGs

Add your DAG files to the `dags/` directory. Changes will be automatically detected and loaded.

### 5. Validate DAGs

```bash
python scripts/validate-dags.py
```

## Production Deployment

### Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/downloads) >= 1.0
- Digital Ocean account with API token
- SSH key pair for server access
- Domain configured in Digital Ocean DNS

### Initial Setup with Terraform

Infrastructure is provisioned using Terraform, which automatically creates and configures the Droplet, firewall, and DNS records.

#### 1. Install Terraform

**macOS:**
```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

**Linux:**
```bash
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

**Verify installation:**
```bash
terraform --version
```

#### 2. Generate SSH Key for Deployment

```bash
# Generate SSH key pair
ssh-keygen -t ed25519 -C "airflow-deploy" -f ~/.ssh/airflow_deploy

# Display public key (needed for Terraform)
cat ~/.ssh/airflow_deploy.pub
```

#### 3. Provision Infrastructure with Terraform

```bash
# Navigate to terraform directory
cd terraform

# Set Terraform input variables
export TF_VAR_do_token="your-api-token"
export TF_VAR_ssh_key_fingerprint="your-existing-do-ssh-key-fingerprint"

# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Apply infrastructure
terraform apply
```

Terraform will create:
- Droplet (s-1vcpu-1gb, Ubuntu 22.04) with Docker pre-installed
- Firewall (ports 22, 80, 443)
- DNS A record (flow.raniendu.dev)

#### 4. Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions, and add the following secrets:

| Secret Name | Description | How to Generate |
|-------------|-------------|-----------------|
| `DO_TOKEN` | Digital Ocean API token | [DO Control Panel → API → Tokens](https://cloud.digitalocean.com/account/api/tokens) |
| `DO_SSH_PRIVATE_KEY` | SSH private key for deployment | Content of `~/.ssh/airflow_deploy` (private key) |
| `DO_SSH_KEY_FINGERPRINT` | Existing SSH key fingerprint in DigitalOcean | DigitalOcean Control Panel → Settings → Security → SSH Keys |
| `AIRFLOW_ADMIN_USER` | Initial Airflow admin username | Choose a username (e.g., `admin`) |
| `AIRFLOW_ADMIN_PASSWORD` | Initial Airflow admin password | Choose a strong password |
| `AIRFLOW_FERNET_KEY` | Fernet key for encrypting secrets | Run: `python scripts/generate-fernet-key.py` |
| `AIRFLOW_WEBSERVER_SECRET_KEY` | Flask secret key for sessions | Run: `python -c "import secrets; print(secrets.token_hex(32))"` |

**Optional (for remote state):**

| Secret Name | Description | How to Generate |
|-------------|-------------|-----------------|
| `SPACES_ACCESS_KEY_ID` | DO Spaces access key | [DO Control Panel → API → Spaces Keys](https://cloud.digitalocean.com/account/api/spaces) |
| `SPACES_SECRET_ACCESS_KEY` | DO Spaces secret key | Generated with access key |

**Important:** Keep these secrets secure and never commit them to the repository.

#### 5. Initialize SSL Certificates

After Terraform provisions the infrastructure, SSH into the Droplet and initialize SSL:

```bash
# Get the Droplet IP from Terraform output
cd terraform
terraform output droplet_ip

# SSH into Droplet
ssh airflow-deploy@$(terraform output -raw droplet_ip)

# Initialize SSL certificates
cd /opt/airflow
bash scripts/init-letsencrypt.sh
```

### Infrastructure Management

#### View Current Infrastructure

```bash
cd terraform
terraform show
terraform output
```

#### Update Infrastructure

```bash
cd terraform
terraform plan    # Preview changes
terraform apply   # Apply changes
```

#### Pause / Resume Infrastructure (Cost Saving)

Infrastructure creation is controlled by `terraform/deployment.auto.tfvars`:

```hcl
infra_enabled = false
```

- `infra_enabled = false`: Terraform destroys/manages this repository's Airflow infrastructure to zero active resources.
- `infra_enabled = true`: Terraform creates/recreates Airflow infrastructure and deployment resumes.

Pause workflow:

1. Set `infra_enabled = false` in `terraform/deployment.auto.tfvars`.
2. Push to `main`.
3. GitHub Actions runs Terraform apply and destroys managed Airflow resources.
4. The application deploy job is skipped automatically when no droplet IP is present.

Resume workflow:

1. Set `infra_enabled = true` in `terraform/deployment.auto.tfvars`.
2. Push to `main`.
3. GitHub Actions provisions infra and runs the deploy job.

#### Destroy Infrastructure

```bash
cd terraform
terraform destroy
```

For detailed Terraform configuration options, see [terraform/README.md](terraform/README.md).

### Automated Deployment

Once setup is complete, deployments are automatic:

1. Push code to the `main` branch
2. GitHub Actions will:
   - Validate DAG syntax
   - Apply Terraform infrastructure changes
   - Deploy to Digital Ocean only when infrastructure is enabled (`infra_enabled=true`)
   - Verify deployment health when deploy runs

View deployment status in the Actions tab of your GitHub repository.

## GitHub Secrets Setup Instructions

### Generating Required Secrets

#### 1. Digital Ocean API Token (`DO_TOKEN`)

1. Go to [Digital Ocean Control Panel → API → Tokens](https://cloud.digitalocean.com/account/api/tokens)
2. Click "Generate New Token"
3. Give it a name and select "Read & Write" scope
4. Copy the token (it won't be shown again)

#### 2. SSH Credentials (`DO_SSH_PRIVATE_KEY` and `DO_SSH_KEY_FINGERPRINT`)

```bash
# Generate SSH key pair
ssh-keygen -t ed25519 -C "airflow-deploy" -f ~/.ssh/airflow_deploy

# Display private key (copy this to DO_SSH_PRIVATE_KEY)
cat ~/.ssh/airflow_deploy

# Display public key (add this key in DigitalOcean first)
cat ~/.ssh/airflow_deploy.pub
```

Copy the **entire private key** including the `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----` lines.
For `DO_SSH_KEY_FINGERPRINT`, copy the fingerprint value from DigitalOcean Settings → Security → SSH Keys.

#### 3. Fernet Key (`AIRFLOW_FERNET_KEY`)

```bash
python scripts/generate-fernet-key.py
```

Copy the generated key.

#### 4. Webserver Secret Key (`AIRFLOW_WEBSERVER_SECRET_KEY`)

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the generated key.

#### 5. Admin Credentials

Choose secure values for:
- `AIRFLOW_ADMIN_USER`: Username for initial admin (e.g., `admin`)
- `AIRFLOW_ADMIN_PASSWORD`: Strong password (use a password manager)

#### 6. (Optional) DO Spaces Keys for Remote State

If using remote Terraform state:
1. Go to [Digital Ocean Control Panel → API → Spaces Keys](https://cloud.digitalocean.com/account/api/spaces)
2. Click "Generate New Key"
3. Copy both the access key (`SPACES_ACCESS_KEY_ID`) and secret key (`SPACES_SECRET_ACCESS_KEY`)

### Adding Secrets to GitHub

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret with the exact name from the table above
5. Paste the corresponding value
6. Click **Add secret**

Repeat for all required secrets (7 minimum, 9 with remote state).

## Project Structure

```
.
├── dags/                          # DAG definitions
│   ├── __init__.py
│   ├── example_dag.py
│   └── utils/
├── terraform/                     # Infrastructure as Code
│   ├── main.tf                   # Primary resource definitions
│   ├── variables.tf              # Input variable declarations
│   ├── outputs.tf                # Output value definitions
│   ├── providers.tf              # Digital Ocean provider config
│   ├── versions.tf               # Version constraints
│   ├── cloud-init.yaml           # Server initialization template
│   ├── backend.tf.example        # Remote state backend example
│   └── README.md                 # Terraform documentation
├── scripts/
│   ├── deploy.sh                 # Deployment script
│   ├── validate-dags.py          # DAG syntax validation
│   ├── create-admin.py           # Admin user creation
│   ├── generate-fernet-key.py    # Fernet key generator
│   ├── init-letsencrypt.sh       # SSL certificate setup
│   └── check-cert.sh             # Certificate status check
├── nginx/
│   └── airflow.conf              # Nginx configuration
├── .github/
│   └── workflows/
│       └── deploy.yml            # CI/CD workflow (includes Terraform)
├── docker-compose.yml             # Production stack
├── docker-compose.local.yml       # Local development
├── Dockerfile                     # Custom Airflow image
├── pyproject.toml                 # Dependencies
└── .env.example                   # Environment template

```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Required variables are documented in `.env.example`.

### Key Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AIRFLOW__CORE__FERNET_KEY` | Encryption key for sensitive data | Production |
| `AIRFLOW__WEBSERVER__SECRET_KEY` | Session management secret | Production |
| `AIRFLOW_ADMIN_USER` | Initial admin username | Production |
| `AIRFLOW_ADMIN_PASSWORD` | Initial admin password | Production |
| `POSTGRES_PASSWORD` | PostgreSQL database password | Production |
| `DOMAIN` | Domain name (flow.raniendu.dev) | Production |
| `AIRFLOW_UID` | User ID for Airflow processes | Optional |

## Airflow Version Management

The project uses Apache Airflow 3.1.7, pinned in the Dockerfile for reproducibility.

### Current Version

Check the Airflow version in the `Dockerfile`:

```dockerfile
FROM apache/airflow:3.1.7-python3.10
```

### Airflow 3.x Changes

Airflow 3.x introduces several breaking changes from 2.x:

- **Webserver command replaced**: Use `airflow api-server` instead of `airflow webserver`
- **User management removed**: User creation via CLI has been removed in Airflow 3.x
- **API v1 removed**: Use `/api/v2` endpoints instead of `/api/v1`
- **Database command**: Use `airflow db migrate` instead of `airflow db init`

### Updating Airflow Version

To update to a newer Airflow version:

1. **Update Dockerfile:**
   ```dockerfile
   FROM apache/airflow:3.1.7-python3.10  # New version
   ```

2. **Update dependencies if needed:**
   ```bash
   uv add "apache-airflow==3.1.7"
   ```

3. **Test locally:**
   ```bash
   docker compose -f docker-compose.local.yml build
   docker compose -f docker-compose.local.yml up
   ```

4. **Deploy to production:**
   ```bash
   git add Dockerfile pyproject.toml
   git commit -m "Update Airflow to 3.1.7"
   git push origin main
   ```

### Version Compatibility

- Python version must match Airflow image (currently 3.10)
- Check [Airflow Release Notes](https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html) for breaking changes
- Test DAGs locally before deploying version updates
- Airflow 3.x requires different CLI commands than 2.x

## Troubleshooting

### Local Development

**Port 8080 already in use:**
```bash
# Change port in docker-compose.local.yml
ports:
  - "8081:8080"  # Use 8081 instead
```

**DAGs not loading:**
```bash
# Check DAG syntax
python scripts/validate-dags.py

# Check Airflow logs
docker-compose -f docker-compose.local.yml logs webserver
```

### Production Deployment

**Deployment fails:**
```bash
# Check GitHub Actions logs in the Actions tab
# SSH into Droplet and check logs
ssh airflow-deploy@<droplet-ip>
cd /opt/airflow
docker-compose logs
```

**SSL certificate issues:**
```bash
# Check certificate status
bash scripts/check-cert.sh

# Renew certificate manually
docker-compose run --rm certbot renew
```

**Health check fails:**
```bash
# Check if services are running
docker-compose ps

# Check webserver logs
docker-compose logs webserver

# Check scheduler logs
docker-compose logs scheduler
```

## Cost Optimization

Current infrastructure costs approximately **$6/month**:
- Droplet (s-1vcpu-1gb): ~$6/month
- Bandwidth: Included (1TB)

To reduce costs further:
- Use Digital Ocean's $200 free credit for new accounts
- Consider spot instances for non-critical workloads
- Monitor resource usage and downgrade if possible

## Security Best Practices

- ✅ All secrets stored in GitHub Secrets or environment variables
- ✅ SSL/TLS encryption via Let's Encrypt
- ✅ Fernet key encryption for Airflow connections
- ✅ Firewall configured (only ports 22, 80, 443 open)
- ✅ SSH key authentication (no password login)
- ✅ Regular security updates via automated deployments

## Contributing

1. Create a feature branch
2. Add/modify DAGs in `dags/` directory
3. Validate DAGs: `python scripts/validate-dags.py`
4. Test locally: `docker-compose -f docker-compose.local.yml up`
5. Push to main branch for automatic deployment

## License

MIT
