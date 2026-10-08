"""Render public runtime plans into an inactive copy of the normal Heavy Ops app layout."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def scalar(value):
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def yaml(value, indent=0):
    prefix = ' ' * indent
    if isinstance(value, dict):
        if not value:
            return prefix + '{}\n'
        result = ''
        for key, item in value.items():
            key = key if re.fullmatch(r'[A-Za-z0-9_./-]+', key) else scalar(key)
            if isinstance(item, str) and '\n' in item:
                result += prefix + key + ': |\n'
                result += ''.join(' ' * (indent + 2) + line + '\n' for line in item.splitlines())
            elif isinstance(item, (dict, list)) and item:
                result += prefix + key + ':\n' + yaml(item, indent + 2)
            else:
                result += prefix + key + ': ' + ('{}' if item == {} else '[]' if item == [] else scalar(item)) + '\n'
        return result
    if isinstance(value, list):
        result = ''
        for item in value:
            rendered = yaml(item, indent + 2) if isinstance(item, (dict, list)) else ' ' * (indent + 2) + scalar(item) + '\n'
            result += prefix + '- ' + rendered[indent + 2:]
        return result
    return prefix + scalar(value) + '\n'


parser = argparse.ArgumentParser()
parser.add_argument('--runtime', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
root = Path(__file__).parent
args.output.mkdir(parents=True, exist_ok=True)
for business in ('mk', 'jm'):
    public = json.loads((root / (business + '-development.json')).read_text())
    with tempfile.TemporaryDirectory(prefix='dealer-gitops-public-') as temporary:
        folder = Path(temporary)
        (folder / 'app.json').write_text(json.dumps(public['application']))
        (folder / 'cluster.json').write_text(json.dumps(public['cluster']))
        result = subprocess.run(['deno', 'run', '--allow-read', str(args.runtime / 'scripts/kubernetes-installation-plan.ts'), str(folder / 'app.json'), str(folder / 'cluster.json')], cwd=args.runtime, env={'PATH': os.environ['PATH']}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    plan = json.loads(result.stdout)
    (args.output / (business + '-helm-values.json')).write_text(json.dumps(plan['resources']['dealer-agent/app/helmrelease.yaml']['spec']['values'], indent=2) + '\n')
    for name, value in plan['resources'].items():
        destination = args.output / 'kubernetes/apps' / plan['namespace'] / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        documents = value if isinstance(value, list) else [value]
        content = ''
        for document in documents:
            content += '---\n'
            if document['kind'] == 'Kustomization' and document['apiVersion'].startswith('kustomize.config.'):
                content += '# yaml-language-server: $schema=https://json.schemastore.org/kustomization\n'
            elif document['kind'] == 'HelmRelease':
                content += '# yaml-language-server: $schema=https://raw.githubusercontent.com/bjw-s-labs/helm-charts/main/charts/other/app-template/schemas/helmrelease-helm-v2.schema.json\n'
            content += yaml(document)
        destination.write_text(content)
    (args.output / (business + '-installation-plan.json')).write_text(json.dumps({key: value for key, value in plan.items() if key != 'resources'}, indent=2) + '\n')
print('Wrote inactive public plans to ' + str(args.output))
