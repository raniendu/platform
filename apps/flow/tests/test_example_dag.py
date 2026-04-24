"""
Unit tests for example_dag.py

Verifies that the example DAG loads correctly and has required attributes.
Requirements: 2.1
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime
from airflow.models import DagBag


def test_dag_loads_without_errors():
    """
    Verify that the example DAG loads without import or syntax errors.
    """
    dag_bag = DagBag(dag_folder=str(project_root / "dags"), include_examples=False)
    
    # Check that there are no import errors
    assert len(dag_bag.import_errors) == 0, f"DAG import errors: {dag_bag.import_errors}"
    
    # Check that the example_dag is loaded
    assert "example_dag" in dag_bag.dags, "example_dag not found in DagBag"


def test_dag_has_required_attributes():
    """
    Verify that the example DAG has all required attributes.
    """
    dag_bag = DagBag(dag_folder=str(project_root / "dags"), include_examples=False)
    
    # Access DAG directly from dags dictionary to avoid database access
    assert "example_dag" in dag_bag.dags, "example_dag not found in DagBag"
    dag = dag_bag.dags["example_dag"]
    
    # Verify DAG exists
    assert dag is not None, "example_dag could not be loaded"
    
    # Verify dag_id
    assert dag.dag_id == "example_dag", f"Expected dag_id 'example_dag', got '{dag.dag_id}'"
    
    # Verify schedule (using newer 'schedule' attribute instead of deprecated 'schedule_interval')
    assert dag.schedule == "@daily", f"Expected schedule '@daily', got '{dag.schedule}'"
    
    # Verify start_date (compare date components since Airflow adds timezone)
    assert dag.start_date.year == 2024, f"Expected year 2024, got {dag.start_date.year}"
    assert dag.start_date.month == 1, f"Expected month 1, got {dag.start_date.month}"
    assert dag.start_date.day == 1, f"Expected day 1, got {dag.start_date.day}"
    
    # Verify catchup is disabled
    assert dag.catchup is False, "Expected catchup to be False"
    
    # Verify tags
    assert "example" in dag.tags, "Expected 'example' tag to be present"
    
    # Verify tasks exist
    task_ids = [task.task_id for task in dag.tasks]
    assert "start" in task_ids, "Task 'start' not found"
    assert "print_hello" in task_ids, "Task 'print_hello' not found"
    assert "end" in task_ids, "Task 'end' not found"
    
    # Verify task count
    assert len(dag.tasks) == 3, f"Expected 3 tasks, found {len(dag.tasks)}"


def test_dag_task_dependencies():
    """
    Verify that the DAG tasks have correct dependencies.
    """
    dag_bag = DagBag(dag_folder=str(project_root / "dags"), include_examples=False)
    
    # Access DAG directly from dags dictionary to avoid database access
    dag = dag_bag.dags["example_dag"]
    
    # Get tasks
    start_task = dag.get_task("start")
    hello_task = dag.get_task("print_hello")
    end_task = dag.get_task("end")
    
    # Verify dependencies: start >> hello_task >> end
    assert hello_task in start_task.downstream_list, "hello_task should be downstream of start"
    assert end_task in hello_task.downstream_list, "end should be downstream of hello_task"
    
    # Verify upstream dependencies
    assert start_task in hello_task.upstream_list, "start should be upstream of hello_task"
    assert hello_task in end_task.upstream_list, "hello_task should be upstream of end"
