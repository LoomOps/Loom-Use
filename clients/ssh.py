"""Optional host access. Local execution needs no SSH or new account."""
import contextlib,ipaddress,itertools,json,re,subprocess
from pathlib import Path
from urllib.parse import urlsplit
from stdio import OpsTransport


def local_addresses():
    try:
        p=subprocess.run(['tailscale','status','--json'],capture_output=True,text=True,timeout=5,check=True)
        value=json.loads(p.stdout)
        own=(value.get('Self') or {}) if isinstance(value,dict) else {}
        addresses=own.get('TailscaleIPs') if isinstance(own,dict) else None
        return {a for a in addresses if isinstance(a,str)} if isinstance(addresses,list) else set()
    except (OSError,ValueError,subprocess.SubprocessError):return set()


@contextlib.contextmanager
def metadata(profile):
    import tempfile
    from setup import atomic_private
    with tempfile.TemporaryDirectory() as temp:
        p=Path(temp)/'client.json'
        atomic_private(p,json.dumps({'endpoint':profile['endpoint'],**({'credential':profile['credential']} if profile.get('credential') else {'authentication':'tailscale'})}))
        transport=OpsTransport(p)
        sequence=itertools.count(1)
        def call(group,action,arguments=None):
            r=transport.rpc({'jsonrpc':'2.0','id':next(sequence),'method':'tools/call','params':{'name':group,'arguments':{'action':action,'arguments':arguments or {}}}})
            if not r or 'error' in r or r['result'].get('isError'):
                raise ValueError(f'Loom {group}.{action} unavailable; check the selected connection and live schema')
            return json.loads(r['result']['content'][0]['text'])
        yield call


def descriptor(profile):
    with metadata(profile) as call:return call('system','ssh')


def inspect(profile,info=None,addresses=None):
    info=descriptor(profile) if info is None else info
    if not isinstance(info,dict):raise ValueError('Invalid SSH connection metadata')
    addresses=local_addresses() if addresses is None else addresses
    expected=urlsplit(profile['endpoint']).hostname
    server=set(info.get('addresses') or [])
    local=bool(server.intersection(addresses))
    loopback=expected=='localhost'
    try:loopback=loopback or ipaddress.ip_address(expected).is_loopback
    except ValueError:pass
    if info.get('host') and info['host']!=expected and not (local and loopback):raise ValueError('SSH host differs from the selected Loom endpoint')
    if local:
        result={**info,'mode':'local','state':'ready','ssh_grant_state':info.get('state'),'next':'Use the current OS account and its filesystem permissions. No SSH registration required.'}
        result.pop('argv',None)
        return result
    if info.get('state')!='enabled':return {**info,'mode':'ssh','next':'Ask the Loom Admin to enable your personal SSH account, or reuse an existing authorized SSH route.'}
    name=info.get('username','')
    if not re.fullmatch(r'loomu_[a-z0-9][a-z0-9_]{0,23}',name) or info.get('port')!=22 or not expected or not re.fullmatch(r'[A-Za-z0-9.-]+',expected):raise ValueError('Invalid SSH connection metadata')
    argv=['ssh','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','-p','22',name+'@'+expected]
    return {**info,'mode':'ssh','argv':argv,'next':'Use existing Tailscale identity. An MCP token is not an SSH password.'}


def doctor(profile):
    result=inspect(profile)
    if result.get('mode')=='local' or result.get('state')!='enabled':return result
    try:
        p=subprocess.run(result['argv'][:1]+['-o','BatchMode=yes']+result['argv'][1:]+['id -un'],capture_output=True,text=True,timeout=15)
        valid=p.returncode==0 and p.stdout.strip()==result['username']
        return {**result,'verified':valid,'check':'remote_account' if valid else 'ssh_authentication_or_host_key',
                'next':result['next'] if valid else 'Check VPN identity, Admin grant and trusted host key. Never disable host key checking.'}
    except (OSError,subprocess.TimeoutExpired):return {**result,'verified':False,'check':'ssh_client_or_network'}
