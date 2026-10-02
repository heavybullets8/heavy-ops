"""Narrow UpCloud trial API helper. Credentials and machine configs stay in /tmp."""
import datetime as dt
import json
import os
from pathlib import Path
import stat
import urllib.error
import urllib.request

PRIVATE = Path(os.environ.get('UPCLOUD_TRIAL_STATE', '/tmp/upcloud-hosting-trial-20261002'))
PURPOSE = 'hosting-trial-20261002'
ZONE = 'us-chi1'


def private_file(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise RuntimeError('Refusing unsafe private file')
    return path.read_text()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Refusing authenticated redirect')


def request(path, data=None, method='GET'):
    if not path.startswith('/') or '..' in path or '://' in path:
        raise ValueError('Invalid API path')
    token = private_file(PRIVATE / 'token').strip()
    req = urllib.request.Request('https://api.upcloud.com/1.3' + path,
        data=None if data is None else json.dumps(data).encode(), method=method,
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json', 'Content-Type': 'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=45) as response:
            body = response.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        try:
            code = json.loads(exc.read()).get('error', {}).get('error_code', 'unknown')
        except Exception:
            code = 'unknown'
        raise RuntimeError(f'UpCloud {method} {path}: HTTP {exc.code}, {code}') from None


def save_private(name, data):
    fd = os.open(PRIVATE / name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(data, output, indent=2)


def state():
    path = PRIVATE / 'resources.json'
    return json.loads(private_file(path)) if path.exists() else {'purpose': PURPOSE, 'zone': ZONE, 'resources': {}}


def guard_trial():
    account = request('/account')['account']
    credits = account['credits_breakdown']
    account_credits = credits['account_credits']
    if account_credits.get('paid_credits', 0) or account_credits.get('debt_credits', 0) or account_credits.get('max_debt', 0):
        raise RuntimeError('This helper is restricted to the free-credit trial')
    free = credits['account_free_credits']['breakdown']
    horizon = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)
    usable = sum(x['free_credits'] for x in free if dt.datetime.fromisoformat(x['free_credits_expire'].replace('Z', '+00:00')) > horizon)
    if usable < 10000:
        raise RuntimeError('Insufficient unexpired trial credits for this bounded test')
    limits = account['resource_limits']
    if limits['cores'] < 5 or limits['memory'] < 9216:
        raise RuntimeError('Trial quota cannot hold the reviewed two-node test')
    return account


def create(kind, payload, label):
    current = state()
    if current['purpose'] != PURPOSE or current['zone'] != ZONE:
        raise RuntimeError('Unexpected trial state')
    if label in current['resources']:
        raise RuntimeError(f'{label} is already recorded; inspect it instead of duplicating it')
    body = payload[kind]
    if body.get('zone') != ZONE or not body.get('title', body.get('name', '')).startswith(PURPOSE):
        raise RuntimeError('Refusing a resource outside the reviewed trial')
    guard_trial()
    result = request('/' + kind, payload, 'POST')[kind]
    current['resources'][label] = {'kind': kind, 'uuid': result['uuid'], 'created_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    save_private('resources.json', current)
    save_private(label + '.json', {kind: result})
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['inventory', 'network', 'bastion', 'talos'])
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.action == 'inventory':
        account = guard_trial()
        servers = request('/server')['servers']['server']
        print(json.dumps({'zone': ZONE, 'trial_cores': account['resource_limits']['cores'], 'trial_memory_mib': account['resource_limits']['memory'], 'servers': [{k: s.get(k) for k in ['uuid','title','state','zone']} for s in servers], 'owned': state()['resources']}, indent=2))
        return
    if args.action == 'network':
        payload = {'network': {'name': PURPOSE + '-private', 'zone': ZONE,
            'ip_networks': {'ip_network': [{'family':'IPv4','address':'10.88.0.0/24','dhcp':'yes','dhcp_default_route':'no'}]},
            'labels': [{'key':'purpose','value':PURPOSE}]}}
        kind = 'network'
    else:
        network = state()['resources']['network']['uuid']
        role = args.action
        is_talos = role == 'talos'
        image = '01000000-0000-4000-8000-000020080100'
        # Trial templates are disabled. The target starts from Debian only to
        # allocate its boot disk; stop it and write Talos offline from the
        # helper. Never overwrite a mounted root filesystem.
        payload = {'server': {'zone': ZONE, 'title': PURPOSE + '-' + role, 'hostname': 'trial-' + role,
            'plan': 'STARTER-4xCPU-8GB' if is_talos else 'STARTER-1xCPU-1GB',
            'metadata': 'yes', 'firewall': 'on',
            'labels': {'label':[{'key':'purpose','value':PURPOSE}]},
            'storage_devices': {'storage_device':[{'action':'clone','storage':image,'title':PURPOSE+'-'+role+'-boot','size':40 if is_talos else 10,'tier':'standard'}]},
            'networking': {'interfaces': {'interface':[
                {'type':'public','ip_addresses': {'ip_address':[{'family':'IPv4'}]}},
                {'type':'private','network':network,'ip_addresses': {'ip_address':[{'family':'IPv4','address':'10.88.0.10' if is_talos else '10.88.0.2'}]}}
            ]}}}}
        if is_talos:
            payload['server']['user_data'] = private_file(PRIVATE / 'talos/controlplane.yaml')
        payload['server']['login_user'] = {'username':'root','create_password':'no','ssh_keys': {'ssh_key': [(PRIVATE/'bastion.pub').read_text().strip()]}}
        if not is_talos:
            payload['server']['user_data'] = '#cloud-config\nssh_pwauth: false\ndisable_root: false\n'
        kind = 'server'
    print(json.dumps({'action':args.action,'zone':ZONE,'apply':args.apply,'plan':payload[kind].get('plan'),'name':payload[kind].get('title',payload[kind].get('name'))}))
    if not args.apply:
        return
    result = create(kind, payload, args.action)
    print(json.dumps({'created':args.action,'uuid':result['uuid'],'state':result.get('state'),'addresses':result.get('ip_addresses')}))


if __name__ == '__main__':
    main()
