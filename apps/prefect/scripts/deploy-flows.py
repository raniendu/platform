#!/usr/bin/env python3
"""
Flow deployment script for Prefect.

Requirements: 7.2, 7.3

This script discovers all flows in the flows/ directory and registers them
with the Prefect server. It creates deployments with appropriate work pool
configurations.

Usage:
    python scripts/deploy-flows.py [--work-pool POOL_NAME] [--api-url URL]

Environment Variables:
    PREFECT_API_URL: Prefect server API URL (default: http://localhost:4200/api)
    WORK_POOL_NAME: Work pool name for deployments (default: default-pool)
"""

import argparse
import importlib
import inspect
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prefect import Flow


def get_prefect_id(result: Any) -> Any:
    """Return an ID from Prefect client methods that may return an object or raw UUID."""
    return getattr(result, "id", result)


def get_deployment_path() -> str:
    """Return the code path visible to the worker process registering deployments."""
    return Path.cwd().resolve().as_posix()


def discover_flows(flows_dir: Path = Path("flows")) -> list[tuple[str, "Flow"]]:
    """
    Discover all Prefect flows in the flows directory.

    Args:
        flows_dir: Path to the flows directory

    Returns:
        List of tuples containing (module_name, flow_object)

    Requirements: 7.2
    """
    flows = []

    try:
        from prefect import Flow
    except ModuleNotFoundError:
        print("✗ Prefect is not installed. Run `uv sync` before deploying flows.")
        return flows

    # Add flows directory to Python path
    sys.path.insert(0, str(flows_dir.parent))

    # Find all Python files in flows directory
    for py_file in flows_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        module_name = f"flows.{py_file.stem}"

        try:
            # Import the module
            module = importlib.import_module(module_name)

            # Find all flow objects in the module
            for name, obj in inspect.getmembers(module):
                if isinstance(obj, Flow):
                    flows.append((module_name, obj))
                    print(f"✓ Discovered flow: {obj.name} from {module_name}")

        except Exception as e:
            print(f"✗ Error importing {module_name}: {e}")
            continue

    return flows


async def register_deployments(
    flows: list[tuple[str, "Flow"]],
    work_pool_name: str,
) -> dict[str, Any]:
    """
    Register all discovered flows with the Prefect server.

    Args:
        flows: List of (module_name, flow) tuples
        work_pool_name: Name of the work pool to use

    Returns:
        Dictionary with registration results

    Requirements: 7.2, 7.3
    """
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import (
        DeploymentScheduleCreate,
        DeploymentUpdate,
    )
    from prefect.client.schemas.schedules import CronSchedule

    results = {
        "successful": [],
        "failed": [],
        "total": len(flows),
    }

    async with get_client() as client:
        for module_name, flow in flows:
            try:
                print(f"Deploying {flow.name}...")

                # Create or get the flow in the server
                try:
                    flow_data = await client.read_flow_by_name(flow.name)
                    flow_id = get_prefect_id(flow_data)
                    print(f"  Using existing flow ID: {flow_id}")
                except Exception:
                    # Flow doesn't exist, create it
                    flow_data = await client.create_flow(flow)
                    flow_id = get_prefect_id(flow_data)
                    print(f"  Created new flow ID: {flow_id}")

                # Construct entrypoint for the worker. The deployment path below
                # anchors this relative module path to the worker's current code dir.
                entrypoint = f"{module_name}:{flow.fn.__name__}"
                deployment_path = get_deployment_path()

                # Define deployments list
                deployments_to_create = []

                if flow.name == "daily-brief":
                    # Special handling for daily-brief: create morning and afternoon schedules
                    deployments_to_create.append(
                        {
                            "name": "morning-brief",
                            "schedule": CronSchedule(
                                cron="0 7 * * *", timezone="America/Los_Angeles"
                            ),
                            "description": "Morning daily brief at 7:00 AM PST",
                            "parameters": {"period_override": "Morning"},
                        }
                    )
                    deployments_to_create.append(
                        {
                            "name": "afternoon-brief",
                            "schedule": CronSchedule(
                                cron="0 16 * * *", timezone="America/Los_Angeles"
                            ),
                            "description": "Afternoon daily brief at 4:00 PM PST",
                            "parameters": {"period_override": "Afternoon"},
                        }
                    )
                else:
                    # Default deployment for other flows
                    deployments_to_create.append(
                        {
                            "name": f"{flow.name}-deployment",
                            "schedule": None,
                            "description": f"Automated deployment for {flow.name}",
                            "parameters": {},
                        }
                    )

                for deploy_config in deployments_to_create:
                    deployment_name = deploy_config["name"]
                    deployment_schedule = deploy_config["schedule"]
                    deployment_description = deploy_config["description"]
                    deployment_parameters = deploy_config["parameters"]

                    deployment_tags = (
                        ["automated", "production", "scheduled"]
                        if deployment_schedule
                        else ["automated", "production"]
                    )
                    # Build schedules list for the Prefect API
                    schedule_objects = []
                    if deployment_schedule:
                        schedule_objects.append(
                            DeploymentScheduleCreate(
                                schedule=deployment_schedule,
                                active=True,
                            )
                        )

                    print(f"  Processing deployment: {deployment_name}")

                    # Check if deployment exists and update, otherwise create
                    try:
                        existing = await client.read_deployment_by_name(
                            f"{flow.name}/{deployment_name}"
                        )
                        await client.update_deployment(
                            deployment_id=existing.id,
                            deployment=DeploymentUpdate(
                                entrypoint=entrypoint,
                                work_pool_name=work_pool_name,
                                path=deployment_path,
                                tags=deployment_tags,
                                description=deployment_description,
                                parameters=deployment_parameters,
                            ),
                        )
                        # Manage schedules separately for existing deployments
                        if schedule_objects:
                            # Remove old schedules and add the new one
                            existing_schedules = await client.read_deployment_schedules(
                                existing.id
                            )
                            for old_sched in existing_schedules:
                                await client.delete_deployment_schedule(
                                    existing.id, old_sched.id
                                )
                            await client.create_deployment_schedules(
                                deployment_id=existing.id,
                                schedules=schedule_objects,
                            )
                        deployment_id = existing.id
                        print(f"    Updated existing deployment: {deployment_name}")
                    except Exception:
                        deployment_id = await client.create_deployment(
                            flow_id=flow_id,
                            name=deployment_name,
                            entrypoint=entrypoint,
                            work_pool_name=work_pool_name,
                            path=deployment_path,
                            tags=deployment_tags,
                            description=deployment_description,
                            schedules=schedule_objects,
                            parameters=deployment_parameters,
                        )
                        print(f"    Created new deployment: {deployment_name}")

                    results["successful"].append(
                        {
                            "flow": flow.name,
                            "module": module_name,
                            "deployment_id": str(deployment_id),
                            "deployment_name": deployment_name,
                        }
                    )
                print(f"✓ Registered deployment: {flow.name}")

            except Exception as e:
                results["failed"].append(
                    {
                        "flow": flow.name,
                        "module": module_name,
                        "error": str(e),
                    }
                )
                print(f"✗ Failed to register {flow.name}: {e}")
                traceback.print_exc()

    return results


async def verify_work_pool(work_pool_name: str) -> bool:
    """
    Verify that the specified work pool exists.

    Args:
        work_pool_name: Name of the work pool to check

    Returns:
        True if work pool exists, False otherwise
    """
    from prefect.client.orchestration import get_client

    try:
        async with get_client() as client:
            work_pools = await client.read_work_pools()
            pool_names = [pool.name for pool in work_pools]

            if work_pool_name in pool_names:
                print(f"✓ Work pool '{work_pool_name}' exists")
                return True
            else:
                print(f"⚠ Work pool '{work_pool_name}' not found")
                print(
                    f"  Available work pools: {', '.join(pool_names) if pool_names else 'none'}"
                )
                print(
                    f"  Deployments will be created but may not run until work pool is created"
                )
                return False

    except Exception as e:
        print(f"⚠ Could not verify work pool: {e}")
        return False


async def main():
    """Main entry point for the deployment script."""
    parser = argparse.ArgumentParser(description="Deploy Prefect flows to the server")
    parser.add_argument(
        "--work-pool",
        default="default-pool",
        help="Work pool name for deployments (default: default-pool)",
    )
    parser.add_argument(
        "--api-url",
        help="Prefect API URL (overrides PREFECT_API_URL env var)",
    )
    parser.add_argument(
        "--flows-dir",
        type=Path,
        default=Path("flows"),
        help="Directory containing flow definitions (default: flows)",
    )

    args = parser.parse_args()

    # Set API URL if provided
    if args.api_url:
        import os

        os.environ["PREFECT_API_URL"] = args.api_url

    print("=" * 60)
    print("Prefect Flow Deployment Script")
    print("=" * 60)
    print()

    # Discover flows
    print("Discovering flows...")
    flows = discover_flows(args.flows_dir)

    if not flows:
        print("⚠ No flows found in flows/ directory; skipping deployment registration")
        return

    print(f"\nFound {len(flows)} flow(s)")
    print()

    # Verify work pool
    print("Verifying work pool...")
    await verify_work_pool(args.work_pool)
    print()

    # Register deployments
    print("Registering deployments...")
    results = await register_deployments(flows, args.work_pool)

    # Print summary
    print()
    print("=" * 60)
    print("Deployment Summary")
    print("=" * 60)
    print(f"Total flows: {results['total']}")
    print(f"Successful: {len(results['successful'])}")
    print(f"Failed: {len(results['failed'])}")

    if results["successful"]:
        print("\n✓ Successfully deployed:")
        for item in results["successful"]:
            print(f"  - {item['flow']} (ID: {item['deployment_id']})")

    if results["failed"]:
        print("\n✗ Failed deployments:")
        for item in results["failed"]:
            print(f"  - {item['flow']}: {item['error']}")
        sys.exit(1)

    print("\n✓ All flows deployed successfully!")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
