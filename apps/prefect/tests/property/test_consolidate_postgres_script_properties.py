from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
CONSOLIDATE_SCRIPT = REPO_ROOT / "deploy" / "scripts" / "consolidate-postgres.sh"


def test_existing_shared_postgres_without_marker_is_verified_then_adopted() -> None:
    script = CONSOLIDATE_SCRIPT.read_text()

    adopt_pos = script.index(
        "Shared Postgres container exists without marker; verifying expected databases before adoption."
    )
    up_pos = script.index('"${compose[@]}" up -d postgres', adopt_pos)
    postgres_pos = script.index(
        'wait_for_postgres "$new_container" postgres postgres', up_pos
    )
    prefect_pos = script.index(
        'wait_for_postgres "$new_container" prefect prefect', postgres_pos
    )
    airflow_pos = script.index(
        'wait_for_postgres "$new_container" airflow airflow', prefect_pos
    )
    marker_pos = script.index("write_marker adopted", airflow_pos)

    assert adopt_pos < up_pos < postgres_pos < prefect_pos < airflow_pos < marker_pos


def test_shared_postgres_with_legacy_containers_refuses_overwrite() -> None:
    script = CONSOLIDATE_SCRIPT.read_text()

    assert (
        "Shared Postgres container exists but marker is absent; refusing to overwrite it."
        in script
    )
