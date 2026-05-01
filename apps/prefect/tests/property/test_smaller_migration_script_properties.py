from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATION_SCRIPT = REPO_ROOT / "deploy" / "scripts" / "migrate-smaller-droplet.sh"


def _function_body(script: str, name: str) -> str:
    marker = f"{name}() {{"
    start = script.index(marker)
    next_function = script.find("\n}\n\n", start)
    assert next_function != -1, f"Could not find end of {name}"
    return script[start : next_function + 3]


def test_start_new_stack_sequences_airflow_init_before_other_heavy_services() -> None:
    script = MIGRATION_SCRIPT.read_text()
    body = _function_body(script, "start_new_stack")
    log_body = _function_body(script, "show_container_logs")

    assert "up --no-build --force-recreate airflow-init" in body
    assert 'show_container_logs "$host" platform-airflow-init' in body
    assert "docker logs --tail 200" in log_body
    assert body.index("airflow-init") < body.index("prefect-server")
    assert 'up -d --no-build"' not in body


def test_stage_quiesces_reused_staging_services_before_database_restore() -> None:
    script = MIGRATION_SCRIPT.read_text()
    body = _function_body(script, "phase_stage")

    assert 'stop_new_runtime_stack "$NEW_IP"' in body
    assert body.index("stop_new_runtime_stack") < body.index("restore_database")
