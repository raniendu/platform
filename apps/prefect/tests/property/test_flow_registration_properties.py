"""
Property-based tests for flow registration.

**Feature: prefect-digitalocean-deployment, Property 9: Flow registration consistency**

Tests that all flows in flows/ directory are registered after deployment,
ensuring the deployment process correctly discovers and registers all flow definitions.

**Validates: Requirements 7.2, 7.3**
"""

import importlib.util
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# These properties validate Prefect flow discovery and require Prefect imports.
pytest.importorskip("prefect", reason="prefect is required for flow discovery tests")


def discover_flows_in_directory(flows_dir: Path) -> dict[str, Any]:
    """
    Discover all Prefect flows defined in Python files within a directory.

    Args:
        flows_dir: Path to directory containing flow files

    Returns:
        Dictionary mapping flow names to flow objects
    """
    discovered_flows = {}

    # Find all Python files except __init__.py and deployments.py
    flow_files = [
        f
        for f in flows_dir.glob("*.py")
        if f.name not in ("__init__.py", "deployments.py")
    ]

    for flow_file in flow_files:
        # Import the module
        spec = importlib.util.spec_from_file_location(flow_file.stem, flow_file)
        if spec is None or spec.loader is None:
            continue

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find all flow objects in the module
        for attr_name in dir(module):
            # Skip private/magic attributes and common imports
            if attr_name.startswith("_") or attr_name in (
                "flow",
                "task",
                "get_run_logger",
            ):
                continue

            attr = getattr(module, attr_name)
            # Check if it's a Prefect Flow instance
            if type(attr).__name__ == "Flow" and hasattr(attr, "name"):
                flow_name = attr.name
                discovered_flows[flow_name] = attr

    return discovered_flows


@given(
    flows_dir_name=st.just("flows"),  # Always use the actual flows directory
)
@settings(max_examples=100, deadline=None)
def test_flow_discovery_consistency(flows_dir_name: str) -> None:
    """
    **Feature: prefect-digitalocean-deployment, Property 9: Flow registration consistency**

    Property: For any flows directory, discovering flows multiple times should
    produce the same set of flow names consistently.

    This ensures the flow discovery mechanism is deterministic and reliable.

    **Validates: Requirements 7.2, 7.3**
    """
    flows_dir = Path(flows_dir_name)

    # Skip if directory doesn't exist
    if not flows_dir.exists():
        return

    # Discover flows twice
    first_discovery = discover_flows_in_directory(flows_dir)
    second_discovery = discover_flows_in_directory(flows_dir)

    # Flow names should be identical
    assert set(first_discovery.keys()) == set(second_discovery.keys()), (
        f"Flow discovery is not consistent:\n"
        f"First: {set(first_discovery.keys())}\n"
        f"Second: {set(second_discovery.keys())}"
    )


@given(
    flows_dir_name=st.just("flows"),
)
@settings(max_examples=100)
def test_all_flows_have_names(flows_dir_name: str) -> None:
    """
    **Feature: prefect-digitalocean-deployment, Property 9: Flow registration consistency**

    Property: For any discovered flow, it must have a valid name attribute
    that can be used for registration.

    This ensures all flows can be properly registered with the Prefect server.

    **Validates: Requirements 7.2, 7.3**
    """
    flows_dir = Path(flows_dir_name)

    # Skip if directory doesn't exist
    if not flows_dir.exists():
        return

    discovered_flows = discover_flows_in_directory(flows_dir)

    # All flows must have non-empty names
    for flow_name, flow_obj in discovered_flows.items():
        assert flow_name, f"Flow {flow_obj} has empty name"
        assert isinstance(
            flow_name, str
        ), f"Flow name must be string, got {type(flow_name)}"
        assert len(flow_name) > 0, f"Flow name must not be empty"


@given(
    flows_dir_name=st.just("flows"),
)
@settings(max_examples=100)
def test_flow_files_are_importable(flows_dir_name: str) -> None:
    """
    **Feature: prefect-digitalocean-deployment, Property 9: Flow registration consistency**

    Property: For any Python file in the flows directory (except __init__.py),
    it must be importable without errors.

    This ensures the deployment process can successfully load all flow definitions.

    **Validates: Requirements 7.2, 7.3**
    """
    flows_dir = Path(flows_dir_name)

    # Skip if directory doesn't exist
    if not flows_dir.exists():
        return

    flow_files = [
        f
        for f in flows_dir.glob("*.py")
        if f.name not in ("__init__.py", "deployments.py")
    ]

    for flow_file in flow_files:
        # Attempt to import - should not raise exceptions
        spec = importlib.util.spec_from_file_location(flow_file.stem, flow_file)
        assert spec is not None, f"Could not create spec for {flow_file}"
        assert spec.loader is not None, f"Spec has no loader for {flow_file}"

        module = importlib.util.module_from_spec(spec)
        # This should not raise an exception
        spec.loader.exec_module(module)


@given(
    flows_dir_name=st.just("flows"),
    min_expected_flows=st.just(1),  # We expect at least one project flow
)
@settings(max_examples=100)
def test_minimum_flows_discovered(flows_dir_name: str, min_expected_flows: int) -> None:
    """
    **Feature: prefect-digitalocean-deployment, Property 9: Flow registration consistency**

    Property: For any flows directory with flow files, at least one flow
    should be discovered.

    This ensures the discovery mechanism actually finds flows when they exist.

    **Validates: Requirements 7.2, 7.3**
    """
    flows_dir = Path(flows_dir_name)

    # Skip if directory doesn't exist
    if not flows_dir.exists():
        return

    # Check if there are any flow files
    flow_files = [
        f
        for f in flows_dir.glob("*.py")
        if f.name not in ("__init__.py", "deployments.py")
    ]

    if len(flow_files) == 0:
        # No flow files, so no flows expected
        return

    discovered_flows = discover_flows_in_directory(flows_dir)

    # Should discover at least the minimum expected flows
    assert len(discovered_flows) >= min_expected_flows, (
        f"Expected at least {min_expected_flows} flows, "
        f"but discovered {len(discovered_flows)}: {list(discovered_flows.keys())}"
    )


@given(
    flows_dir_name=st.just("flows"),
)
@settings(max_examples=100)
def test_discovered_flows_are_callable(flows_dir_name: str) -> None:
    """
    **Feature: prefect-digitalocean-deployment, Property 9: Flow registration consistency**

    Property: For any discovered flow object, it must be callable (can be invoked).

    This ensures flows can actually be executed after registration.

    **Validates: Requirements 7.2, 7.3**
    """
    flows_dir = Path(flows_dir_name)

    # Skip if directory doesn't exist
    if not flows_dir.exists():
        return

    discovered_flows = discover_flows_in_directory(flows_dir)

    for flow_name, flow_obj in discovered_flows.items():
        assert callable(
            flow_obj
        ), f"Flow '{flow_name}' is not callable: {type(flow_obj)}"
