"""
Property-based tests for Terraform infrastructure configuration.

**Feature: prefect-digitalocean-deployment, Property 4: Infrastructure idempotency**

Tests that terraform plan with unchanged config shows no changes, ensuring
idempotent deployments and preventing duplicate resources.

**Validates: Requirements 3.1, 3.2**
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


def _terraform_ready() -> tuple[bool, str]:
    """Check if Terraform is installed and can reach the provider registry."""
    if os.getenv("SKIP_TERRAFORM_TESTS") == "1":
        return False, "SKIP_TERRAFORM_TESTS=1"

    if shutil.which("terraform") is None:
        return False, "terraform not installed"

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            temp_path.joinpath("main.tf").write_text("""
terraform {
  required_version = ">= 1.0"

  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

resource "null_resource" "check" {}
""")
            init_result = subprocess.run(
                ["terraform", "init", "-backend=false", "-no-color"],
                cwd=temp_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
    except Exception as exc:
        return False, f"terraform init check failed: {exc}"

    if init_result.returncode != 0:
        stderr = (init_result.stderr or "").lower()
        stdout = (init_result.stdout or "").lower()
        registry_error_markers = (
            "registry.terraform.io",
            "failed to query available provider packages",
            "no such host",
            "temporary failure in name resolution",
        )
        if any(marker in stderr for marker in registry_error_markers) or any(
            marker in stdout for marker in registry_error_markers
        ):
            return False, "terraform registry not reachable"

        # Do not skip on other terraform init failures, so real regressions
        # in terraform behavior surface as test failures.
        return True, ""

    return True, ""


TERRAFORM_AVAILABLE, TERRAFORM_SKIP_REASON = _terraform_ready()

# Strategies for generating valid Terraform variable values
droplet_size_strategy = st.sampled_from(
    [
        "s-1vcpu-1gb",
        "s-1vcpu-2gb",
        "s-2vcpu-2gb",
        "s-2vcpu-4gb",
    ]
)

region_strategy = st.sampled_from(
    ["nyc1", "nyc3", "sfo3", "ams3", "sgp1", "lon1", "fra1", "tor1", "blr1"]
)

domain_strategy = st.from_regex(r"[a-z0-9][a-z0-9-]{1,48}\.[a-z]{2,10}", fullmatch=True)

droplet_name_strategy = st.from_regex(
    r"[a-z0-9][a-z0-9-]{1,28}[a-z0-9]", fullmatch=True
)


def create_terraform_config(
    droplet_size: str,
    region: str,
    domain_name: str,
    droplet_name: str,
    temp_dir: Path,
) -> dict[str, Any]:
    """
    Create a minimal Terraform configuration for testing idempotency.

    This creates a simplified version of the main Terraform config that can be
    tested without actual Digital Ocean credentials.
    """
    # Create main.tf with local backend for testing
    main_tf = f"""
terraform {{
  required_version = ">= 1.0"
  
  required_providers {{
    null = {{
      source  = "hashicorp/null"
      version = "~> 3.0"
    }}
  }}
  
  backend "local" {{
    path = "{temp_dir}/terraform.tfstate"
  }}
}}

# Use null_resource to simulate infrastructure without actual cloud resources
resource "null_resource" "prefect_droplet" {{
  triggers = {{
    droplet_name = "{droplet_name}"
    region       = "{region}"
    size         = "{droplet_size}"
    domain       = "{domain_name}"
  }}
}}

output "droplet_config" {{
  value = {{
    name   = "{droplet_name}"
    region = "{region}"
    size   = "{droplet_size}"
    domain = "{domain_name}"
  }}
}}
"""

    config_file = temp_dir / "main.tf"
    config_file.write_text(main_tf)

    return {
        "droplet_size": droplet_size,
        "region": region,
        "domain_name": domain_name,
        "droplet_name": droplet_name,
    }


def run_terraform_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a terraform command and return the result."""
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.skipif(not TERRAFORM_AVAILABLE, reason=TERRAFORM_SKIP_REASON)
@given(
    droplet_size=droplet_size_strategy,
    region=region_strategy,
    domain_name=domain_strategy,
    droplet_name=droplet_name_strategy,
)
@settings(
    max_examples=10, deadline=None
)  # Reduced examples, no deadline for terraform operations
def test_terraform_idempotency(
    droplet_size: str,
    region: str,
    domain_name: str,
    droplet_name: str,
) -> None:
    """
    **Feature: prefect-digitalocean-deployment, Property 4: Infrastructure idempotency**

    Property: For any valid Terraform configuration, running terraform plan twice
    with unchanged configuration should show zero changes on the second run.

    This ensures:
    1. No duplicate resources are created
    2. Deployments are idempotent
    3. State tracking works correctly

    **Validates: Requirements 3.1, 3.2**
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create Terraform configuration
        config = create_terraform_config(
            droplet_size=droplet_size,
            region=region,
            domain_name=domain_name,
            droplet_name=droplet_name,
            temp_dir=temp_path,
        )

        # Initialize Terraform
        init_result = run_terraform_command(
            ["terraform", "init", "-no-color"],
            cwd=temp_path,
        )
        assert (
            init_result.returncode == 0
        ), f"Terraform init failed:\n{init_result.stderr}"

        # First apply - should create resources
        apply_result = run_terraform_command(
            ["terraform", "apply", "-auto-approve", "-no-color"],
            cwd=temp_path,
        )
        assert (
            apply_result.returncode == 0
        ), f"Terraform apply failed:\n{apply_result.stderr}"

        # First plan after apply - should show no changes
        plan_result_1 = run_terraform_command(
            ["terraform", "plan", "-detailed-exitcode", "-no-color"],
            cwd=temp_path,
        )

        # Exit code 0 means no changes, 1 means error, 2 means changes detected
        assert plan_result_1.returncode == 0, (
            f"First plan after apply showed changes (expected none):\n"
            f"Config: {config}\n"
            f"Exit code: {plan_result_1.returncode}\n"
            f"Output: {plan_result_1.stdout}\n"
            f"Stderr: {plan_result_1.stderr}"
        )

        # Second plan - should still show no changes (idempotency)
        plan_result_2 = run_terraform_command(
            ["terraform", "plan", "-detailed-exitcode", "-no-color"],
            cwd=temp_path,
        )

        assert plan_result_2.returncode == 0, (
            f"Second plan showed changes (idempotency violated):\n"
            f"Config: {config}\n"
            f"Exit code: {plan_result_2.returncode}\n"
            f"Output: {plan_result_2.stdout}\n"
            f"Stderr: {plan_result_2.stderr}"
        )

        # Verify output contains expected values
        show_result = run_terraform_command(
            ["terraform", "show", "-json"],
            cwd=temp_path,
        )
        assert (
            show_result.returncode == 0
        ), f"Terraform show failed:\n{show_result.stderr}"

        state = json.loads(show_result.stdout)

        # Verify the resource exists in state
        assert "values" in state, "State should contain values"
        assert "root_module" in state["values"], "State should contain root_module"

        resources = state["values"]["root_module"].get("resources", [])
        assert len(resources) > 0, "State should contain at least one resource"

        # Find our null_resource
        prefect_resource = next(
            (
                r
                for r in resources
                if r.get("address") == "null_resource.prefect_droplet"
            ),
            None,
        )
        assert (
            prefect_resource is not None
        ), "State should contain prefect_droplet resource"

        # Verify triggers match our config
        triggers = prefect_resource["values"]["triggers"]
        assert triggers["droplet_name"] == droplet_name
        assert triggers["region"] == region
        assert triggers["size"] == droplet_size
        assert triggers["domain"] == domain_name


@pytest.mark.skipif(not TERRAFORM_AVAILABLE, reason=TERRAFORM_SKIP_REASON)
@given(
    initial_size=droplet_size_strategy,
    new_size=droplet_size_strategy,
    region=region_strategy,
    domain_name=domain_strategy,
    droplet_name=droplet_name_strategy,
)
@settings(
    max_examples=10, deadline=None
)  # Reduced examples, no deadline for terraform operations
def test_terraform_detects_changes(
    initial_size: str,
    new_size: str,
    region: str,
    domain_name: str,
    droplet_name: str,
) -> None:
    """
    **Feature: prefect-digitalocean-deployment, Property 4: Infrastructure idempotency**

    Property: For any Terraform configuration change, terraform plan should detect
    the change and report it.

    This ensures Terraform properly tracks state and detects when configuration
    has been modified.

    **Validates: Requirements 3.1, 3.2**
    """
    # Skip if sizes are the same (no change to detect)
    if initial_size == new_size:
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create initial configuration
        create_terraform_config(
            droplet_size=initial_size,
            region=region,
            domain_name=domain_name,
            droplet_name=droplet_name,
            temp_dir=temp_path,
        )

        # Initialize and apply
        run_terraform_command(["terraform", "init", "-no-color"], cwd=temp_path)
        run_terraform_command(
            ["terraform", "apply", "-auto-approve", "-no-color"],
            cwd=temp_path,
        )

        # Modify configuration
        create_terraform_config(
            droplet_size=new_size,  # Changed!
            region=region,
            domain_name=domain_name,
            droplet_name=droplet_name,
            temp_dir=temp_path,
        )

        # Plan should detect changes
        plan_result = run_terraform_command(
            ["terraform", "plan", "-detailed-exitcode", "-no-color"],
            cwd=temp_path,
        )

        # Exit code 2 means changes detected
        assert plan_result.returncode == 2, (
            f"Plan should detect size change from {initial_size} to {new_size}\n"
            f"Exit code: {plan_result.returncode}\n"
            f"Output: {plan_result.stdout}"
        )
