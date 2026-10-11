"""Validated artifact build and real GitHub Pages workflow generation."""
from pathlib import Path
import json
from flwu.site import build_site


class PublishError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(f'[{code}] {message}')


def build_deployable(archive_dir, output_dir):
    """Build from reviewed public exports, never copy arbitrary private folders."""
    return build_site(archive_dir, Path(output_dir) / 'dist')


def publish_workflow_config(branch='main'):
    return {
        'name': 'GitHub Pages',
        'on': {'push': {'branches': [branch], 'paths': ['website/updates/**', 'src/flwu/**', 'pyproject.toml', '.github/workflows/pages.yml']},
               'pull_request': {'paths': ['website/updates/**', 'src/flwu/**', 'tests/**', 'pyproject.toml', '.github/workflows/pages.yml']},
               'workflow_dispatch': {}},
        'permissions': {'contents': 'read'},
        'concurrency': {'group': 'pages-${{ github.ref }}', 'cancel-in-progress': False},
        'jobs': {
            'build': {'runs-on': 'ubuntu-latest', 'steps': [
                {'uses': 'actions/checkout@v6'},
                {'uses': 'actions/setup-python@v6', 'with': {'python-version': '3.13'}},
                {'name': 'Install', 'run': 'python -m pip install . pytest'},
                {'name': 'Test', 'run': 'PYTHONDONTWRITEBYTECODE=1 python -m pytest -q'},
                {'name': 'Build reviewed public archive', 'run': 'PYTHONDONTWRITEBYTECODE=1 flwu publish --archive website/updates --output build/site'},
                {'uses': 'actions/upload-pages-artifact@v4', 'with': {'path': 'build/site'}},
            ]},
            'deploy': {
                'if': "github.event_name != 'pull_request' && github.ref == 'refs/heads/" + branch + "'",
                'needs': 'build', 'runs-on': 'ubuntu-latest',
                'permissions': {'pages': 'write', 'id-token': 'write'},
                'environment': {'name': 'github-pages', 'url': '${{ steps.deployment.outputs.page_url }}'},
                'steps': [{'uses': 'actions/configure-pages@v5'},
                          {'name': 'Deploy', 'id': 'deployment', 'uses': 'actions/deploy-pages@v4'}],
            },
        },
    }


def write_github_workflow(workflow_dir):
    """JSON is a YAML 1.2 subset and is accepted by GitHub workflow parsing."""
    workflow_dir = Path(workflow_dir)
    workflow_dir.mkdir(parents=True, exist_ok=True)
    path = workflow_dir / 'pages.yml'
    path.write_text(json.dumps(publish_workflow_config(), indent=2) + '\n', encoding='utf-8')
    return path
