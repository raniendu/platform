"""
Property-based tests for deployment configuration consistency.

Tests that the Prefect worker image contains required flow dependencies and
that shared production Compose passes all necessary environment variables.

**Validates: Requirements 7.3, 7.4**
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
MONOREPO_ROOT = PROJECT_ROOT.parent.parent

FLOW_DEPENDENCIES = ["google-genai", "httpx", "python-dotenv"]
FLOW_IMPORT_CHECKS = [
    "import httpx",
    "from dotenv import load_dotenv",
    "from google import genai",
]

REQUIRED_WORKER_ENV_VARS = [
    "PUSHOVER_APP_TOKEN",
    "PUSHOVER_USER_KEY",
    "GEMINI_API_KEY",
]

DEPLOY_WORKFLOW = MONOREPO_ROOT / ".github" / "workflows" / "deploy.yml"


class TestWorkerDependencyInstallation:
    """Tests that the worker image installs flow dependencies."""

    def test_pyproject_declares_flow_runtime_dependencies(self) -> None:
        """
        Flow imports must live in runtime dependencies so the process pool
        worker can execute deployments without runtime package installs.
        """
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()

        for dep in FLOW_DEPENDENCIES:
            assert (
                f'"{dep}' in content
            ), f"pyproject.toml must declare runtime dependency '{dep}'"

    def test_prefect_dockerfile_syncs_runtime_dependencies(self) -> None:
        """The Prefect image must install locked runtime dependencies at build time."""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text()

        assert "COPY pyproject.toml uv.lock" in content
        assert "uv sync --frozen --no-dev" in content

    def test_start_worker_verifies_flow_dependencies_before_worker_start(self) -> None:
        """
        The worker startup script should verify imports before polling, without
        downloading packages during container startup.
        """
        worker_script = PROJECT_ROOT / "docker" / "prefect" / "start-worker.sh"
        content = worker_script.read_text()

        verify_pos = content.find("import httpx")
        worker_pos = content.find("prefect worker start")

        assert verify_pos != -1, "start-worker.sh must verify flow dependencies"
        assert worker_pos != -1, "start-worker.sh must contain 'prefect worker start'"
        assert (
            verify_pos < worker_pos
        ), "dependency verification must run before worker start"
        assert "uv pip install" not in content
        assert "curl -LsSf https://astral.sh/uv/install.sh" not in content

        for import_check in FLOW_IMPORT_CHECKS:
            assert (
                import_check in content
            ), f"start-worker.sh must verify '{import_check}' before starting"


class TestDeployWorkflowEnvVars:
    """Tests that shared Compose passes required env vars."""

    def test_docker_compose_prod_references_required_env_vars(self) -> None:
        """
        Shared production Compose must reference worker env vars so values
        from .env.production or GitHub Secrets reach the worker container.
        """
        compose_file = MONOREPO_ROOT / "deploy" / "compose" / "docker-compose.prod.yml"
        assert compose_file.exists(), f"{compose_file} does not exist"

        content = compose_file.read_text()

        for var in REQUIRED_WORKER_ENV_VARS:
            assert f"${{{var}}}" in content, (
                f"docker-compose.prod.yml worker service must reference "
                f"${{{var}}} so the secret reaches the container"
            )


class TestDeployWorkflowRegistersFlows:
    """Tests that production deploy registers Prefect flow deployments."""

    def test_deploy_workflow_registers_prefect_flows_after_compose_start(self) -> None:
        """
        Production deploy must register flows after Prefect containers start so
        the UI contains deployment records for the bundled flow code.
        """
        content = DEPLOY_WORKFLOW.read_text()

        assert "name: Register Prefect deployments" in content
        assert "if: needs.build-images.outputs.deploy_prefect == 'true'" in content
        assert "platform-prefect-server" in content
        assert "platform-prefect-worker" in content
        assert "exec -T prefect-worker" in content
        assert "python /app/scripts/setup-blocks.py" in content
        assert "python /app/scripts/deploy-flows.py" in content
        assert "--api-url http://prefect-server:4200/api" in content
        assert "--work-pool" in content

        setup_pos = content.find("python /app/scripts/setup-blocks.py")
        deploy_pos = content.find("python /app/scripts/deploy-flows.py")
        assert setup_pos < deploy_pos
