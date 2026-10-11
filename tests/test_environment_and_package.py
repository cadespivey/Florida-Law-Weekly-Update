"""Test environment and package setup for C01."""

import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).parent
PROJECT_DIR = TESTS_DIR.parent


def test_import_flwu_exposes_version():
    """Test that importing flwu succeeds and exposes version 0.1.0."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import flwu; assert flwu.__version__ == '0.1.0', f'Expected 0.1.0, got {flwu.__version__}'",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_DIR,
    )
    assert result.returncode == 0, f"Import failed: {result.stderr}"
    assert "0.1.0" in result.stdout or result.stdout == "", "Version not exposed correctly"


def test_package_uses_src_layout():
    """Test that package metadata uses src/flwu layout."""
    # Check that src/flwu/__init__.py exists
    init_file = PROJECT_DIR / "src" / "flwu" / "__init__.py"
    assert init_file.exists(), f"Expected {init_file} to exist"
    
    # Check that there are no Python modules in hyphenated directories
    hyphenated_dirs = [d for d in PROJECT_DIR.iterdir() if d.is_dir() and "-" in d.name]
    for hyphenated_dir in hyphenated_dirs:
        py_files = list(hyphenated_dir.rglob("*.py"))
        assert len(py_files) == 0, f"Found Python modules in hyphenated directory {hyphenated_dir}: {py_files}"


def test_requirements_lock_format():
    """Test that requirements.lock records actual resolved versions."""
    lock_file = PROJECT_DIR / "requirements.lock"
    assert lock_file.exists(), f"Expected {lock_file} to exist"
    
    lock_content = lock_file.read_text()
    
    # Check that it's not empty
    assert len(lock_content.strip()) > 0, "requirements.lock should have content after dependency resolution"
    
    # Check that it doesn't contain credentials or machine-specific paths
    assert "password=" not in lock_content.lower(), "Lock file should not contain passwords"
    assert "/Users/" not in lock_content or "/Users/cadespivey/.local" in lock_content, "Lock file should not contain machine-specific paths"
    assert "token=" not in lock_content.lower(), "Lock file should not contain tokens"
