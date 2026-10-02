"""Manage the isolated UpCloud trial without using the home cluster context."""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess

ROOT = Path(__file__).resolve().parent
PRIVATE = Path(os.environ.get('UPCLOUD_TRIAL_STATE', '/tmp/upcloud-hosting-trial-20261002'))
NODE = '10.88.0.10'
CONTEXT = 'admin@upcloud-trial'
SOCKET = PRIVATE / 'management-ssh.sock'


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def private(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid():
        raise RuntimeError(f'Expected an owned private file: {path.name}')
    return path


def ssh():
    data = json.loads(private(PRIVATE / 'bastion.json').read_text())['server']
    if data['title'] != 'hosting-trial-20261002-bastion' or data['zone'] != 'us-chi1':
        raise RuntimeError('Unexpected bastion identity')
    addresses = data['ip_addresses']['ip_address']
    ip = next(x['address'] for x in addresses if x['access'] == 'public' and x['family'] == 'IPv4')
    return ['ssh', '-i', str(private(PRIVATE / 'bastion')), '-S', str(SOCKET),
            '-o', f'UserKnownHostsFile={PRIVATE / "known_hosts"}',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'BatchMode=yes',
            '-o', 'ConnectTimeout=10', f'root@{ip}']


def talos(*args):
    return ['talosctl', '--talosconfig', str(private(PRIVATE / 'talos/talosconfig')),
            '--context', 'upcloud-trial', '--endpoints', '127.0.0.1:15000', '--nodes', NODE, *args]


def kubectl(*args):
    return ['kubectl', '--kubeconfig', str(private(PRIVATE / 'kubeconfig')),
            '--context', CONTEXT, *args]


def guard_cluster():
    result = run(kubectl('config', 'view', '--minify', '-o', 'json'), capture_output=True, text=True)
    config = json.loads(result.stdout)
    cluster = config['clusters'][0]
    if cluster['name'] != 'upcloud-trial' or cluster['cluster']['server'] != 'https://127.0.0.1:16443':
        raise RuntimeError('Refusing any kubeconfig other than the isolated trial')
    run(kubectl('get', '--raw=/readyz'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['connect', 'disconnect', 'version', 'bootstrap', 'kubeconfig', 'install', 'status'])
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == 'connect':
        command = ssh()
        if subprocess.run(command[0:-1] + ['-O', 'check', command[-1]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            print('Management tunnel already running')
            return
        run(command[0:-1] + ['-M', '-N', '-f', '-o', 'ExitOnForwardFailure=yes',
            '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=4',
            '-L', f'127.0.0.1:15000:{NODE}:50000', '-L', f'127.0.0.1:16443:{NODE}:6443', command[-1]])
    elif args.action == 'disconnect':
        command = ssh()
        run(command[0:-1] + ['-O', 'exit', command[-1]])
    elif args.action == 'version':
        run(talos('version'))
    elif args.action == 'bootstrap':
        # Run exactly once per newly installed control plane.
        run(talos('bootstrap'))
    elif args.action == 'kubeconfig':
        run(talos('kubeconfig', str(PRIVATE / 'kubeconfig'), '--merge=false', '--force'))
        os.chmod(PRIVATE / 'kubeconfig', 0o600)
        run(kubectl('config', 'set-cluster', 'upcloud-trial', '--server=https://127.0.0.1:16443', '--tls-server-name=' + NODE))
        guard_cluster()
    elif args.action == 'install':
        guard_cluster()
        env = os.environ.copy()
        env['KUBECONFIG'] = str(PRIVATE / 'kubeconfig')
        env['HELMFILE_CACHE_HOME'] = str(PRIVATE / 'helmfile-cache')
        run(['helmfile', '--kube-context', CONTEXT, '--file', str(ROOT / 'bootstrap/helmfile.yaml'), 'sync', '--hide-notes'], env=env)
    elif args.action == 'status':
        run(talos('version'))
        guard_cluster()
        run(kubectl('get', 'nodes', '-o', 'wide'))
        run(kubectl('get', 'pods', '-A'))
        run(kubectl('-n', 'flux-system', 'get', 'fluxinstances'))


if __name__ == '__main__':
    main()
