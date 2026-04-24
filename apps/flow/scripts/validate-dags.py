#!/usr/bin/env python3
"""
DAG Syntax Validation Script

This script validates all DAG files in the dags/ directory by attempting to import them
and checking for syntax errors. It returns proper exit codes for CI/CD integration.

Exit Codes:
    0 - All DAGs are valid
    1 - One or more DAGs have syntax errors or import failures
"""

import sys
import os
from pathlib import Path
from importlib import util as import_util
import traceback


def validate_dag_file(dag_file_path: Path) -> tuple[bool, str]:
    """
    Validate a single DAG file by attempting to import it.
    
    Args:
        dag_file_path: Path to the DAG file to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Create a module spec from the file
        spec = import_util.spec_from_file_location(
            f"dag_module_{dag_file_path.stem}",
            dag_file_path
        )
        
        if spec is None or spec.loader is None:
            return False, f"Could not load module spec for {dag_file_path}"
        
        # Load the module
        module = import_util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        return True, ""
        
    except SyntaxError as e:
        error_msg = f"Syntax error in {dag_file_path}:\n"
        error_msg += f"  Line {e.lineno}: {e.msg}\n"
        error_msg += f"  {e.text}"
        return False, error_msg
        
    except Exception as e:
        error_msg = f"Error loading {dag_file_path}:\n"
        error_msg += f"  {type(e).__name__}: {str(e)}\n"
        error_msg += traceback.format_exc()
        return False, error_msg


def find_dag_files(dags_directory: Path) -> list[Path]:
    """
    Find all Python files in the DAGs directory.
    
    Args:
        dags_directory: Path to the dags directory
        
    Returns:
        List of paths to Python files (excluding __init__.py)
    """
    dag_files = []
    
    for file_path in dags_directory.rglob("*.py"):
        # Skip __init__.py files
        if file_path.name == "__init__.py":
            continue
        dag_files.append(file_path)
    
    return sorted(dag_files)


def main() -> int:
    """
    Main validation function.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Determine the dags directory path
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    dags_dir = project_root / "dags"
    
    # Check if dags directory exists
    if not dags_dir.exists():
        print(f"ERROR: DAGs directory not found at {dags_dir}", file=sys.stderr)
        return 1
    
    # Add project root to Python path so imports work
    sys.path.insert(0, str(project_root))
    
    # Find all DAG files
    dag_files = find_dag_files(dags_dir)
    
    if not dag_files:
        print(f"WARNING: No DAG files found in {dags_dir}")
        return 0
    
    print(f"Validating {len(dag_files)} DAG file(s)...\n")
    
    # Validate each DAG file
    all_valid = True
    results = []
    
    for dag_file in dag_files:
        relative_path = dag_file.relative_to(project_root)
        is_valid, error_msg = validate_dag_file(dag_file)
        
        if is_valid:
            results.append((relative_path, True, ""))
            print(f"✓ {relative_path}")
        else:
            results.append((relative_path, False, error_msg))
            print(f"✗ {relative_path}")
            all_valid = False
    
    # Print detailed error messages
    if not all_valid:
        print("\n" + "=" * 80)
        print("VALIDATION ERRORS:")
        print("=" * 80 + "\n")
        
        for path, is_valid, error_msg in results:
            if not is_valid:
                print(f"{path}:")
                print(error_msg)
                print()
    
    # Print summary
    print("=" * 80)
    valid_count = sum(1 for _, is_valid, _ in results if is_valid)
    total_count = len(results)
    
    if all_valid:
        print(f"SUCCESS: All {total_count} DAG file(s) are valid")
        return 0
    else:
        print(f"FAILURE: {valid_count}/{total_count} DAG file(s) are valid")
        return 1


if __name__ == "__main__":
    sys.exit(main())
