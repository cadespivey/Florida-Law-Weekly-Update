"""Pytest configuration for Florida Litigator Weekly Update tests."""

import pytest


@pytest.fixture
def temporary_directory(tmp_path):
    """Provide a temporary directory for tests."""
    return tmp_path
