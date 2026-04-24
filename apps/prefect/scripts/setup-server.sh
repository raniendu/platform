#!/bin/bash
set -euo pipefail

# Server Setup Script for Prefect Digital Ocean Droplet
# This script configures a fresh Ubuntu Droplet with Docker, Docker Compose,
# and basic security hardening.

echo "=== Prefect Server Setup ==="
echo "Starting initial server configuration..."

# Update system packages
echo "Updating system packages..."
apt-get update
apt-get upgrade -y

# Install required packages
echo "Installing required packages..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    ufw \
    fail2ban

# Install Docker
echo "Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    systemctl enable docker
    systemctl start docker
    echo "Docker installed successfully"
else
    echo "Docker already installed"
fi

# Install Docker Compose
echo "Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "Docker Compose installed successfully"
else
    echo "Docker Compose already installed"
fi

# Configure UFW firewall
echo "Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable
echo "Firewall configured"

# Configure fail2ban for SSH protection
echo "Configuring fail2ban..."
systemctl enable fail2ban
systemctl start fail2ban

# SSH hardening
echo "Hardening SSH configuration..."
SSH_CONFIG="/etc/ssh/sshd_config"
cp ${SSH_CONFIG} ${SSH_CONFIG}.backup

# Disable password authentication (key-only)
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' ${SSH_CONFIG}
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' ${SSH_CONFIG}

# Disable root login
sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' ${SSH_CONFIG}
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' ${SSH_CONFIG}

# Restart SSH service
systemctl restart sshd

# Create directory for Prefect deployment
echo "Creating deployment directory..."
mkdir -p /opt/prefect
cd /opt/prefect

# Set up log rotation for Docker
echo "Configuring Docker log rotation..."
cat > /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
systemctl restart docker

echo ""
echo "=== Setup Complete ==="
echo "Server is ready for Prefect deployment"
echo ""
echo "Next steps:"
echo "1. Deploy docker-compose.prod.yml to /opt/prefect"
echo "2. Configure environment variables"
echo "3. Run: docker-compose -f docker-compose.prod.yml up -d"
echo ""
echo "Firewall status:"
ufw status
echo ""
echo "Docker version:"
docker --version
echo ""
echo "Docker Compose version:"
docker-compose --version
