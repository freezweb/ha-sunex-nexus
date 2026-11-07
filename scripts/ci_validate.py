"""Run official validators unchanged on Jenkins, without a Docker dependency."""
import json
import hashlib
import io
import os
from pathlib import Path
import platform
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / '.ci-reports'
REPORTS.mkdir(exist_ok=True)
UV = ROOT / '.ci-tools/uv'
CORE_SHA = '74cf5a49c63ed8d4d87717844bf14f79c28c9cea'
HACS_SHA = 'a15e87ec0d1c82e58f1ddbaf17669d3eaa261eb8'


def run(args, *, cwd=ROOT, env=None, report=None):
    if report:
        result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        output = result.stdout
        if env and env.get('INPUT_GITHUB_TOKEN'):
            output = output.replace(env['INPUT_GITHUB_TOKEN'], '[REDACTED]')
        (REPORTS / report).write_text(output)
        print(output, flush=True)
        result.check_returncode()
    else:
        subprocess.run([str(a) for a in args], cwd=cwd, env=env, check=True)


def checkout(name, remote, revision):
    path = ROOT / name
    if not (path / '.git').exists():
        run(['git', 'init', path])
        run(['git', 'remote', 'add', 'origin', remote], cwd=path)
    run(['git', 'fetch', '--depth', '1', 'origin', revision], cwd=path)
    run(['git', 'checkout', '--detach', revision], cwd=path)
    return path


def environment(name):
    path = ROOT / (name + '-py3145')
    if not (path / 'bin/python').exists():
        run([UV, 'venv', '--python', '3.14.5', path])
    return path / 'bin/python'


def install(python, *requirements):
    run([UV, 'pip', 'install', '--python', python, *requirements])


mode = sys.argv[1]
if mode == 'bootstrap':
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise RuntimeError('This CI bootstrap requires Linux x86_64')
    if not UV.exists() or not subprocess.check_output([UV, '--version'], text=True).startswith('uv 0.13.5 '):
        metadata = json.load(urllib.request.urlopen('https://pypi.org/pypi/uv/0.13.5/json', timeout=30))
        artifact = next(row for row in metadata['urls'] if
                        row['filename'].endswith('manylinux_2_17_x86_64.manylinux2014_x86_64.whl'))
        payload = urllib.request.urlopen(artifact['url'], timeout=60).read()
        assert hashlib.sha256(payload).hexdigest() == artifact['digests']['sha256']
        with zipfile.ZipFile(io.BytesIO(payload)) as wheel:
            binary = next(name for name in wheel.namelist() if Path(name).name == 'uv')
            UV.parent.mkdir(exist_ok=True)
            UV.write_bytes(wheel.read(binary))
        UV.chmod(0o755)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    (REPORTS / 'sources.json').write_text(json.dumps({
        'integration_commit': commit, 'hassfest_core_commit': CORE_SHA,
        'hacs_validator_commit': HACS_SHA, 'runner': 'Jenkins',
        'ignored_checks': [], 'production_device_access': False,
    }, indent=2))
    environment('.ci-tests')
elif mode == 'tests':
    python = environment('.ci-tests')
    install(python, '-e', str(ROOT), 'pytest-homeassistant-custom-component==0.13.375')
    run([python, '-m', 'pytest', '-q', '--tb=short', '--disable-socket',
         '--allow-unix-socket', '--allow-hosts=127.0.0.1', '--junitxml=.ci-reports/tests.xml'], report='tests.txt')
elif mode == 'hassfest':
    core = checkout('.ci-core', 'https://github.com/home-assistant/core.git', CORE_SHA)
    python = environment('.ci-hassfest')
    install(python, '-r', str(core / 'requirements.txt'), 'pipdeptree', 'tqdm', 'ruff')
    install(python, '--no-deps', '--config-settings', 'editable_mode=compat', '-e', str(core / 'packages/hassfest'))
    run([python, '-m', 'script.hassfest', '--action', 'validate', '--integration-path',
         ROOT / 'custom_components/sunex_nexus'], cwd=core, report='hassfest.txt')
elif mode == 'hacs':
    source = checkout('.ci-hacs-source', 'https://github.com/hacs/integration.git', HACS_SHA)
    python = environment('.ci-hacs')
    install(python, '-r', str(source / 'requirements_action.txt'))
    env = os.environ.copy()
    if not env.get('INPUT_GITHUB_TOKEN'):
        raise RuntimeError('Protected Jenkins GitHub credential is required')
    env.update({'PYTHONPATH': str(source), 'GITHUB_WORKSPACE': str(ROOT),
                'GITHUB_REPOSITORY': 'freezweb/ha-sunex-nexus', 'GITHUB_ACTOR': 'freezweb',
                'INPUT_CATEGORY': 'integration', 'INPUT_IGNORE': '',
                'REPOSITORY_REF': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()})
    # Credentials are passed only in the child environment, not argv or a file.
    run([python, source / 'action/action.py'], cwd=source, env=env, report='hacs.txt')
else:
    raise ValueError('Unknown CI stage')
