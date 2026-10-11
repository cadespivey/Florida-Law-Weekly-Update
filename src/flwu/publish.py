"""GitHub Pages publishing (C39).

Coordinates building, staging, and deploying a production release
to GitHub Pages. Does not push to repositories directly — produces
the deployable artifact and metadata.
"""
from __future__ import annotations
from typing import Any
from pathlib import Path
import json

class PublishError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")

def build_deployable(site_dir, output_dir):
    """Build a deployable site package."""
    dist = output_dir / "dist"
    dist.mkdir(parents=True, exist_ok=True)

    import shutil
    for item in site_dir.iterdir():
        if item.is_file():
            shutil.copy2(item, dist / item.name)
        elif item.is_dir():
            target = dist / item.name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)

    return dist

def publish_workflow_config(branch="main"):
    return {
        "name": "GitHub Pages",
        "on": {"push": {"branches": [branch]}},
        "jobs": {
            "deploy": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {"name": "Deploy", "run": "echo Deploy site"},
                ],
            },
        },
    }

def write_github_workflow(workflow_dir):
    workflow_dir.mkdir(parents=True, exist_ok=True)
    workflow_file = workflow_dir / "pages.yml"
    config = publish_workflow_config()
    workflow_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return workflow_file
