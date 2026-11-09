"""Optional host access. Local execution needs no SSH or new account."""
import ipaddress,json,re,subprocess
from pathlib import Path
from urllib.parse import urlsplit
from stdio import OpsTransport


def local_addresses():
    try:
        p=subprocess.run(['tailscale','status','--json'],capture_output=True,text=True,timeout=5,check=True)
        return set(json.loads(p.stdout).get('Self',{}).get('TailscaleIPs',[]))
    except (OSError,ValueError,subprocess.SubprocessError):return set()


def descriptor(profile):
    import tempfile
    from setup import atomic_private
    with tempfile.TemporaryDirectory() as temp:
        p=Path(temp)/'client.json'
        atomic_private(p,json.dumps({'endpoint':profile['endpoint'],**({'credential':profile['credential']} if profile.get('credential') else {'authentication':'tailscale'})}))
        transport=OpsTransport(p)
        r=transport.rpc({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'system','arguments':{'action':'ssh'}}})
        if not r or 'error' in r or r['result'].get('isError'):raise ValueError('SSH connection discovery unavailable; update Loom or ask its Admin')
        return json.loads(r['result']['content'][0]['text'])


def inspect(profile,info=None,addresses=None):
    info=descriptor(profile) if info is None else info
    addresses=local_addresses() if addresses is None else addresses
    expected=urlsplit(profile['endpoint']).hostname
    if info.get('host') and info['host']!=expected:raise ValueError('SSH host differs from the selected Loom endpoint')
    server=set(info.get('addresses',[]))
    if server.intersection(addresses):
        return {'mode':'local','state':'ready','next':'Use the current OS account and its filesystem permissions. No SSH registration required.'}
    if info.get('state')!='enabled':return {'mode':'ssh',**info,'next':'Ask the Loom Admin to enable your personal SSH account.'}
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
