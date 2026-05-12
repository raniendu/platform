from __future__ import annotations

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
