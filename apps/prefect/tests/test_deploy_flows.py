from __future__ import annotations

import asyncio
import importlib.util
import types
from pathlib import Path
from uuid import uuid4


def load_deploy_flows_module() -> types.ModuleType:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "deploy-flows.py"
    spec = importlib.util.spec_from_file_location("deploy_flows", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_get_prefect_id_accepts_object_with_id() -> None:
    module = load_deploy_flows_module()
    flow_id = uuid4()

    assert module.get_prefect_id(types.SimpleNamespace(id=flow_id)) == flow_id


def test_get_prefect_id_accepts_raw_uuid() -> None:
    module = load_deploy_flows_module()
    flow_id = uuid4()

    assert module.get_prefect_id(flow_id) == flow_id


def test_register_deployments_uses_registration_cwd_for_code_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    module = load_deploy_flows_module()
    registration_cwd = tmp_path / "app"
    registration_cwd.mkdir()
    captured_deployments = []

    def example_flow() -> None:
        pass

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def read_flow_by_name(self, name: str):
            return types.SimpleNamespace(id=uuid4())

        async def read_deployment_by_name(self, name: str):
            raise RuntimeError("deployment does not exist")

        async def create_deployment(self, **kwargs):
            captured_deployments.append(kwargs)
            return uuid4()

    def fake_get_client():
        return FakeClient()

    monkeypatch.chdir(registration_cwd)
    monkeypatch.setattr("prefect.client.orchestration.get_client", fake_get_client)

    flow = types.SimpleNamespace(name="example-flow", fn=example_flow)

    asyncio.run(module.register_deployments([("flows.example", flow)], "default-pool"))

    assert captured_deployments[0]["path"] == str(registration_cwd)
