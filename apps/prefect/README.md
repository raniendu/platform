# Prefect Digital Ocean Deployment

A complete infrastructure setup for running Prefect Open Source on Digital Ocean with automated CI/CD via GitHub Actions.

## Overview

This project provides a production-ready Prefect workflow orchestration platform with:

- **Local Development**: Docker Compose environment for developing and testing flows
- **Automated Deployment**: GitHub Actions CI/CD pipeline for infrastructure and application deployment
- **Minimal Cost**: Single Digital Ocean Droplet (~$6-11/month)
- **Secure Access**: SSL certificates via Let's Encrypt and basic authentication
- **Infrastructure as Code**: Terraform for reproducible infrastructure

**Live Instance**: https://prefect.raniendu.dev

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Digital Ocean Droplet                     │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │   Nginx    │──│    Prefect   │──│    PostgreSQL       │ │
│  │ (SSL+Auth) │  │    Server    │  │    (Database)       │ │
│  └────────────┘  └──────────────┘  └─────────────────────┘ │
│                   ┌──────────────┐                          │
│                   │   Prefect    │                          │
│                   │    Worker    │                          │
│                   └──────────────┘                          │
└─────────────────────────────────────────────────────────────┘
         ▲                                    ▲
         │                                    │
    HTTPS (443)                      GitHub Actions
    Basic Auth                       (Terraform + Deploy)
```

## Quick Start

### Prerequisites

- Python 3.10+
- Prefect 3.6.25+
- Docker and Docker Compose
- UV package manager
- Digital Ocean account (for production)
- GitHub account (for CI/CD)

### Local Development Setup

1. **Install dependencies**:
   ```bash
   uv sync
   ```

2. **Start local Prefect environment**:
   ```bash
   ./scripts/local-up.sh
   ```

3. **Access Prefect UI**:
   Open http://localhost:4200 in your browser

4. **Run a flow**:
   ```bash
   python flows/<your_flow>.py
   ```

5. **Stop local environment**:
   ```bash
   ./scripts/local-down.sh
   ```

## Creating and Testing Flows

### Flow Structure

Flows are defined in the `flows/` directory. Each flow is a Python file with Prefect decorators:

```python
from prefect import flow, task

@task
def my_task(value: str) -> str:
    return f"Processed: {value}"

@flow(name="my-flow")
def my_flow(input_value: str = "default"):
    result = my_task(input_value)
    return result

if __name__ == "__main__":
    my_flow()
```

### Testing Flows Locally

1. **Ensure local environment is running**:
   ```bash
   ./scripts/local-up.sh
   ```

2. **Run your flow directly**:
   ```bash
   python flows/your_flow.py
   ```

3. **Or deploy and run via Prefect**:
   ```bash
   # Deploy the flow
   python scripts/deploy-flows.py
   
   # Run via Prefect CLI
   prefect deployment run 'your-flow/your-flow-deployment'
   ```

4. **Monitor in Prefect UI**:
   Visit http://localhost:4200 to see flow runs, logs, and results

### Flow Development Tips

- **Use tasks**: Break complex logic into `@task` decorated functions for better observability
- **Add logging**: Use `get_run_logger()` for structured logging
- **Test locally first**: Always test flows in local environment before pushing
- **Use parameters**: Make flows configurable with parameters for different environments
- **Handle errors**: Use Prefect's retry mechanisms and error handling

## Documentation

- **[Development Guide](docs/DEVELOPMENT_GUIDE.md)** - Creating, testing, and managing flows
- **[Complete Setup Guide](docs/COMPLETE_SETUP_GUIDE.md)** - Full deployment setup (Digital Ocean, GitHub, DNS)


## Daily Brief Verification Model

The `daily-brief` flow now uses a grounded pipeline with a strict verification gate.

- **No URL, no headline**: news candidates without a valid `source_url` are rejected.
- Every verified news item must include `headline`, `summary`, `source_url`, `publisher_name`, `published_timestamp`, and `evidence_snippet`.
- Candidates are verified before rendering; rejected candidates are excluded from user-facing output.
- If no verified items remain in a section, the flow renders a safe fallback (for example, `No verified updates available.`).
- Market facts are fetched from a structured source (Yahoo Finance chart API) and rendered directly; prose rewriting may happen after facts are assembled but cannot add new facts.

### Safe provider extension checklist

When adding a new news or market provider:

1. Return structured candidate records with source metadata and evidence snippets.
2. Route candidates through `verify_news_candidates` before rendering.
3. Keep deterministic checks (required fields, URL validity, evidence support) in front of any LLM step.
4. Ensure fallbacks are preserved when no verified records pass validation.

### Verification-focused tests

Run verification and rendering tests with:

```bash
pytest tests/property/test_daily_brief_behavior.py
```

## Production Deployment

### First-Time Setup

Follow the **[Complete Setup Guide](docs/COMPLETE_SETUP_GUIDE.md)** which covers:

1. Digital Ocean account setup (API token, SSH keys)
2. GitHub repository secrets configuration
3. DNS configuration (Squarespace)
4. First deployment checklist

### Automated Deployment

Once configured, deployments are automatic:

1. **Push to main branch**:
   ```bash
   git push origin main
   ```

2. **GitHub Actions will**:
   - Provision/update infrastructure with Terraform
   - Deploy Docker containers to Droplet
   - Register all flows with Prefect server

3. **Monitor deployment**:
   - Check GitHub Actions tab for workflow status
   - Access Prefect UI at https://prefect.raniendu.dev

## Project Structure

```
.
├── flows/                      # Prefect flow definitions
│   ├── <your_flow>.py          # Project flow definitions
├── config/                     # Environment configuration
│   └── settings.py             # Pydantic config models
├── terraform/                  # Infrastructure as Code
│   ├── main.tf                 # Digital Ocean resources
│   ├── backend.tf              # Remote state config
│   ├── variables.tf            # Input variables
│   └── outputs.tf              # Output values
├── docker/                     # Docker configurations
│   ├── nginx/                  # Nginx reverse proxy
│   └── certbot/                # SSL certificates
├── scripts/                    # Deployment scripts
│   ├── local-up.sh             # Start local environment
│   ├── local-down.sh           # Stop local environment
│   ├── setup-server.sh         # Initial server setup
│   └── deploy-flows.py         # Flow registration
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   ├── property/               # Property-based tests
│   └── integration/            # Integration tests
├── docs/                       # Documentation
├── .github/workflows/          # CI/CD pipelines
├── docker-compose.local.yml    # Local development stack
├── docker-compose.prod.yml     # Production stack
└── pyproject.toml              # Python dependencies
```

## Common Commands

### Local Development

```bash
# Start local environment
./scripts/local-up.sh

# Stop local environment
./scripts/local-down.sh

# View logs
docker compose -f docker-compose.local.yml logs -f

# Run a flow
python flows/<your_flow>.py

# Deploy flows to local server
python scripts/deploy-flows.py
```

### Dependency Management

```bash
# Install dependencies
uv sync

# Add new dependency
uv add package-name

# Update lock file
uv lock
```

### Testing

```bash
# Run all tests
pytest tests/

# Run specific test types
pytest tests/unit/
pytest tests/property/
pytest tests/integration/

# Run with coverage
pytest --cov=flows --cov=config tests/
```

### Infrastructure

```bash
# Initialize Terraform
cd terraform
terraform init

# Preview changes
terraform plan

# Apply changes
terraform apply

# Destroy infrastructure
terraform destroy
```

## Configuration

### Environment Variables

**Local Development**:
- `PREFECT_API_URL`: Set automatically by docker-compose.local.yml

**Production** (via GitHub Secrets):
- `DO_TOKEN`: Digital Ocean API token
- `DO_SSH_PRIVATE_KEY`: SSH private key for Droplet access
- `DO_SSH_KEY_FINGERPRINT`: SSH key fingerprint
- `PREFECT_AUTH_USERNAME`: Basic auth username
- `PREFECT_AUTH_PASSWORD`: Basic auth password
- `POSTGRES_PASSWORD`: Database password
- `PUSHOVER_APP_TOKEN`: Pushover application API token for notifications
- `PUSHOVER_USER_KEY`: Pushover user key for notifications

See [Complete Setup Guide](docs/COMPLETE_SETUP_GUIDE.md) for details.

## Monitoring and Troubleshooting

### Accessing Logs

**Local**:
```bash
docker compose -f docker-compose.local.yml logs -f [service-name]
```

**Production** (SSH to Droplet):
```bash
ssh root@prefect.raniendu.dev
cd /opt/prefect
docker compose -f docker-compose.prod.yml logs -f [service-name]
```

### Common Issues

**Local environment won't start**:
- Check Docker is running: `docker ps`
- Check port 4200 is available: `lsof -i :4200`
- View logs: `docker compose -f docker-compose.local.yml logs`

**Flow won't run**:
- Ensure Prefect server is healthy
- Check work pool exists and worker is running
- View flow run logs in Prefect UI

**Production deployment fails**:
- Check GitHub Actions logs
- Verify all secrets are configured
- Ensure DNS is properly configured

## Cost Breakdown

| Resource | Monthly Cost | Notes |
|----------|--------------|-------|
| Digital Ocean Droplet (s-1vcpu-1gb) | $6 | 1 vCPU, 1GB RAM, 25GB SSD |
| Digital Ocean Spaces (optional) | $5 | For Terraform state storage |
| Let's Encrypt SSL | Free | Auto-renewed certificates |
| GitHub Actions | Free | 2,000 minutes/month free tier |

**Total: $6-11/month**

## Security

- **SSL/TLS**: All traffic encrypted via Let's Encrypt certificates
- **Authentication**: Basic auth protects Prefect UI and API
- **Firewall**: UFW configured to allow only ports 22, 80, 443
- **SSH**: Password authentication disabled, key-only access
- **Secrets**: All sensitive values stored in GitHub Secrets

## Contributing

1. Create a new branch for your changes
2. Test locally using `./scripts/local-up.sh`
3. Run tests: `pytest tests/`
4. Push and create a pull request

## License

MIT

## Support

For issues and questions:
- Check the [Development Guide](docs/DEVELOPMENT_GUIDE.md) for flow development
- Check the [Complete Setup Guide](docs/COMPLETE_SETUP_GUIDE.md) for deployment issues
- Review [GitHub Issues](../../issues)
- Consult [Prefect documentation](https://docs.prefect.io/)
