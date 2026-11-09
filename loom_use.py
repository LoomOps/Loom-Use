#!/usr/bin/env python3
"""Loom Use: user-scoped connection profiles and explicit client lifecycle."""
import argparse, contextlib, fcntl, getpass, hashlib, json, os, re, shlex, shutil
import subprocess, sys, tempfile, tomllib, uuid, functools
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'clients'))
from setup import atomic_private, private_directory, config_text, verify, check_config
from headers import read_token
from stdio import NoRedirect
import releases, codex_runtime, diagnostics
import ssh as ssh_client


def endpoint(value):
    p=urlsplit(value)
    if (p.scheme not in ('http','https') or not p.hostname or p.username or p.password
        or p.query or p.fragment or p.path not in ('','/','/mcp')
        or (p.scheme=='http' and p.hostname not in ('127.0.0.1','localhost','::1'))):
        raise ValueError('Use a private HTTPS Loom origin or /mcp URL')
    return value.rstrip('/') if p.path=='/mcp' else value.rstrip('/')+'/mcp'


def resolve(value):
    target=endpoint(value)
    if urlsplit(value).path=='/mcp': return target
    # Public Gateway discloses its private origin without operational access.
    try:
        with build_opener(NoRedirect()).open(Request(value.rstrip('/')+'/api/session'),timeout=5) as r:
            session=json.loads(r.read(65536))
        if session.get('mode')=='invite' and session.get('dashboard'):
            proposed=endpoint(session['dashboard'])
            if urlsplit(proposed).hostname != urlsplit(value).hostname:
                raise ValueError('Gateway advertises another hostname; provide its private URL explicitly')
            return proposed
    except (HTTPError,URLError,TimeoutError,json.JSONDecodeError): pass
    return target


def local_identity():
    try:
        r=subprocess.run(['tailscale','status','--json'],capture_output=True,text=True,timeout=4,check=True)
        d=json.loads(r.stdout)
        if not isinstance(d,dict):raise ValueError('Invalid local status')
        own=d.get('Self') or {}
        if not isinstance(own,dict):raise ValueError('Invalid local identity')
        return {'state':d.get('BackendState'),'tagged':bool(own.get('Tags'))}
    except (OSError,subprocess.SubprocessError,ValueError): return {'state':'unknown','tagged':None}


def checked_name(name):
    if not re.fullmatch('[A-Za-z0-9_-]{1,80}',name):raise ValueError('Use a simple connection name')
    return name


def path_plan(home=None, skill_root=None):
    paths=[Path(home or os.environ.get('CODEX_HOME',Path.home()/'.codex')).expanduser().absolute(),
           Path(skill_root or Path.home()/'.agents/skills').expanduser().absolute()]
    result=[]
    for target in paths:
        existing=target;missing=[]
        while not existing.exists():
            missing.append(existing);existing=existing.parent
        result.append({'target':str(target),'nearest_existing_parent':str(existing),
                       'creation_root':str(missing[-1]) if missing else None,
                       'write_scope':str(missing[-1] if missing else target)})
    return {'paths':result,'note':'Sandbox grants must cover missing parents too. This is a path plan, not proof of write permission.'}


def transactional(method):
    @functools.wraps(method)
    def run(self,*args,**kwargs):
        files={p:p.read_bytes() if p.exists() else None for p in (self.config,self.index)}
        links={self.skill_root/n:os.readlink(self.skill_root/n) if (self.skill_root/n).is_symlink() else None for n in ('loom-use','loom-ssh')}
        previous=getattr(self,'_transaction_writes',None)
        writes=self._transaction_writes={}
        try:return method(self,*args,**kwargs)
        except BaseException:
            for p,data in files.items():
                # Never undo another writer's change, including a detected race
                # before this transaction wrote anything.
                if p not in writes or p.is_symlink() or not p.is_file() or p.read_bytes()!=writes[p]:continue
                if data is None:p.unlink()
                else:atomic_private(p,data.decode())
            for link,old_link in links.items():
                if link in writes and link.is_symlink() and os.readlink(link)==writes[link]:
                    link.unlink()
                    if old_link is not None:link.symlink_to(old_link)
            raise
        finally:self._transaction_writes=previous
    return run


class Client:
    def __init__(self, home=None, skill_root=None):
        self.home=Path(home or os.environ.get('CODEX_HOME',Path.home()/'.codex')).expanduser().absolute()
        self.root=private_directory(self.home/'loom-use')
        self.config=self.home/'config.toml'
        self.skill_root=Path(skill_root or Path.home()/'.agents/skills')
        self.index=self.root/'connections.json'

    @contextlib.contextmanager
    def lock(self):
        fd=os.open(self.root/'.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX);yield

    def load(self):
        return json.loads(self.index.read_text()) if self.index.exists() else {'schema':1,'active':None,'connections':{}}

    def write(self,path,text):
        atomic_private(path,text)
        if getattr(self,'_transaction_writes',None) is not None:self._transaction_writes[path]=text.encode()

    def save(self,state):self.write(self.index,json.dumps(state,indent=2)+'\n')

    def prepare_skills(self):
        plan=path_plan(self.home,self.skill_root)
        try:
            self.skill_root.mkdir(parents=True,exist_ok=True)
            # Test actual sandbox permissions before token entry/download/config writes.
            with tempfile.TemporaryFile(dir=self.skill_root):pass
        except PermissionError as exc:
            raise PermissionError('Skill directory is not writable; grant access to '+plan['paths'][1]['write_scope']) from exc

    def refresh(self,name,cwd,thread_id=None):
        result=codex_runtime.reconnect(name,cwd,thread_id)
        if result.get('status')=='pending':
            result['incident_id']=diagnostics.record('loom-use','refresh',code=result.get('reason','refresh_pending'),directory=self.root/'diagnostics',build=(ROOT/'VERSION').read_text().strip())
        return result

    def probe(self,url,credential=None):
        with tempfile.TemporaryDirectory(dir=self.root) as t:
            folder=Path(t); value={'endpoint':url,'authentication':'tailscale'}
            if credential: value={'endpoint':url,'credential':str(credential)}
            atomic_private(folder/'client.json',json.dumps(value))
            return verify(folder)

    def adopt(self,name,url):
        """Find a former static helper only for the exact configured endpoint."""
        if not self.config.exists(): return None
        existing=tomllib.loads(self.config.read_text()).get('mcp_servers',{}).get(name,{})
        if existing.get('url')!=url: return None
        args=shlex.split(existing.get('http_headers_helper',''))
        if len(args)!=3 or Path(args[1]).name!='headers.py': return None
        credential=Path(args[2])
        read_token(credential)  # permission and ownership check; never print
        return credential

    def entry(self,profile):
        value={'url':profile['endpoint']}
        if profile.get('credential'):
            value['http_headers_helper']=shlex.join([sys.executable,str(Path(profile['release_path'])/'clients/headers.py'),profile['credential']])
        return value

    def register(self,name,profile,replace=False):
        check_config(self.config)
        original=self.config.read_text() if self.config.exists() else ''
        current=tomllib.loads(original).get('mcp_servers',{}).get(name)
        state=self.load()
        previous=state['connections'].get(state['active'] if name=='loom-use' else name)
        if current and previous and current not in (self.entry(previous),self.entry(profile)):
            raise ValueError('MCP registration changed outside this client; retained')
        if replace and current and current.get('url')!=profile['endpoint']:
            active=state['connections'].get(state['active'])
            if not active or current!=self.entry(active):
                raise ValueError('Default MCP registration changed outside this client; retained')
            # config_text protects endpoint changes; remove only the owned table first.
            original_for_edit=remove_table(original,name)
        else: original_for_edit=original
        updated=config_text(original_for_edit,name,self.entry(profile))
        if (self.config.read_text() if self.config.exists() else '')!=original:raise ValueError('Configuration changed concurrently')
        if original:atomic_private(self.config.with_name('config.toml.loom-use-backup'),original)
        self.write(self.config,updated)

    def skill(self,release,name='loom-use'):
        if name not in ('loom-use','loom-ssh'):raise ValueError('Unknown Skill')
        target=Path(release)/'skills'/name
        if not (target/'SKILL.md').is_file():raise ValueError('Skill missing')
        self.skill_root.mkdir(parents=True,exist_ok=True)
        link=self.skill_root/name
        if link.exists() and not link.is_symlink():raise ValueError('Existing custom Skill retained; choose another skill root')
        if link.is_symlink():
            old=link.resolve(strict=False)
            if not (old.is_relative_to(self.root) or old.is_relative_to(Path('/loom/loom_use')) or old==ROOT/'skills'/name):
                raise ValueError('Unmanaged Skill link retained')
        temporary=link.with_name('.'+name+'-new')
        if temporary.exists() or temporary.is_symlink():raise ValueError('Pending Skill change exists')
        temporary.symlink_to(target);os.replace(temporary,link)
        if getattr(self,'_transaction_writes',None) is not None:self._transaction_writes[link]=str(target)
        if name=='loom-use' and (self.skill_root/'loom-ssh').is_symlink():self.skill(release,'loom-ssh')

    @transactional
    def ssh(self,operation,name=None):
        state=self.load();name=checked_name(name or state['active'] or 'loom-use');profile=state['connections'][name]
        if operation=='install':
            releases.verify(Path(profile['release_path']),profile['release'])
            self.skill(profile['release_path'],'loom-ssh')
            return {'skill':'loom-ssh','installed':True,'account_created':False}
        # Verify machine identity before obtaining or updating connection metadata.
        report=self.probe(profile['endpoint'],Path(profile['credential']) if profile.get('credential') else None)
        if report['machine_id']!=profile['machine_id']:raise ValueError('Server identity changed')
        result=ssh_client.doctor(profile) if operation=='doctor' else ssh_client.inspect(profile)
        profile['ssh']=result;self.save(state)
        return result

    @transactional
    def connect(self,url,name='loom-use',token=None,authentication='auto',cwd=None,thread_id=None):
        name=checked_name(name);cwd=Path(cwd or Path.cwd())
        if not cwd.is_dir():raise ValueError('Project directory does not exist')
        self.prepare_skills()
        url=resolve(url);state=self.load();old=state['connections'].get(name)
        if old and old['endpoint']!=url:raise ValueError('Connection name targets another Loom; use --name then connections use')
        if authentication not in ('auto','token','tailscale'):raise ValueError('Unknown authentication mode')
        if authentication=='tailscale' and token is not None:raise ValueError('Tailscale mode must not carry a token')
        credential=None if authentication=='tailscale' else (Path(old['credential']) if old and old.get('credential') else self.adopt(name,url))
        temporary=None
        try:
            if token is not None:
                temporary=tempfile.TemporaryDirectory(dir=self.root);credential=Path(temporary.name)/'credential.json'
                atomic_private(credential,json.dumps({'token':token}))
            if credential:
                report=self.probe(url,credential)
            else:
                if authentication=='token' or (authentication=='auto' and local_identity()['tagged']):
                    raise PermissionError('admin_token_required')
                report=self.probe(url)
            if old and old['machine_id']!=report['machine_id']:raise ValueError('Server identity changed; disconnect the old profile before rebinding')
            lock=report['manifest'].get('client_release')
            if not lock:raise ValueError('Server needs a Loom release with independent client handoff')
            release=releases.install(lock,self.root/'releases')
            folder=private_directory(self.root/'profiles'/name)
            if temporary:
                destination=folder/('credential-'+uuid.uuid4().hex+'.json');atomic_private(destination,credential.read_text());credential=destination
            profile={'endpoint':url,'credential':str(credential) if credential else None,
                     'authentication':'token' if credential else 'tailscale','machine_id':report['machine_id'],
                     'release_path':str(release),'release':lock,'revision':report['manifest']['revision']}
            # Refuse name collisions before replacing a shared Skill link.
            self.register(name,profile)
            if state['active']==name and name!='loom-use':self.register('loom-use',profile,replace=True)
            self.skill(release)
            state['connections'][name]=profile
            if state['active'] is None:
                if name!='loom-use':self.register('loom-use',profile)
                state['active']=name
            self.save(state)
            return {'connection':name,'endpoint':url,'server':report,'runtime':self.refresh(name,cwd,thread_id)}
        finally:
            if temporary:temporary.cleanup()

    def doctor(self,name,cwd,thread_id=None,refresh=False):
        state=self.load();name=checked_name(name or state['active'] or 'loom-use');p=state['connections'][name]
        report=self.probe(p['endpoint'],Path(p['credential']) if p.get('credential') else None)
        if report['machine_id']!=p['machine_id']:raise ValueError('Endpoint now identifies another Loom; reconnect explicitly')
        configured=tomllib.loads(self.config.read_text()).get('mcp_servers',{}).get('loom-use' if state['active']==name else name)
        registration='loom-use' if state['active']==name else name
        inactive_default=name=='loom-use' and state['active']!=name
        if configured!=self.entry(p) and not inactive_default:raise ValueError('Codex registration differs from connection profile')
        if inactive_default:refresh=False
        runtime=self.refresh(registration,cwd,thread_id) if refresh else {'status':'unverified'}
        return {'connection':name,'transport':report,'client_update_required':report['manifest'].get('client_release')!=p['release'],
                'guide_update_required':report['manifest']['revision']!=p.get('revision'),'runtime':runtime,'registration':'inactive_profile' if inactive_default else 'configured'}

    @transactional
    def update(self,name,cwd,thread_id=None):
        state=self.load();name=name or state['active'];old=state['connections'][name]
        report=self.probe(old['endpoint'],Path(old['credential']) if old.get('credential') else None)
        if report['machine_id']!=old['machine_id']:raise ValueError('Server identity changed')
        lock=report['manifest']['client_release'];release=releases.install(lock,self.root/'releases')
        new={**old,'release':lock,'release_path':str(release),'revision':report['manifest']['revision']}
        registration='loom-use' if state['active']==name else name
        if not (name=='loom-use' and state['active']!=name):self.register(registration,new)
        if name!='loom-use' and registration!=name:self.register(name,new)
        self.skill(release)
        state['connections'][name]=new;self.save(state)
        runtime=({'status':'unverified','reason':'inactive_profile'} if name=='loom-use' and state['active']!=name else codex_runtime.reconnect(registration,cwd,thread_id))
        # Pending app access is not a failed transport update. Retain the verified
        # new profile and previous release; runtime readiness remains explicit.
        return {'updated':old['release']!=lock,'connection':name,'runtime':runtime,'previous_release_retained':old['release']['version']}

    @transactional
    def use(self,name,cwd,thread_id=None):
        state=self.load();p=state['connections'][checked_name(name)]
        report=self.probe(p['endpoint'],Path(p['credential']) if p.get('credential') else None)
        if report['machine_id']!=p['machine_id']:raise ValueError('Server identity changed')
        releases.verify(Path(p['release_path']),p['release'])
        self.register('loom-use',p,replace=True);self.skill(p['release_path'])
        state['active']=name;self.save(state)
        return {'active':name,'endpoint':p['endpoint'],'runtime':self.refresh('loom-use',cwd,thread_id)}

    @transactional
    def disconnect(self,name):
        state=self.load();name=checked_name(name)
        if name not in state['connections']:raise ValueError('Unknown connection')
        check_config(self.config)
        original=self.config.read_text();text=original;profile=state['connections'][name]
        owned=[]
        if name!='loom-use' or state['active']==name:owned.append(name)
        if state['active']==name:owned.append('loom-use')
        configured=tomllib.loads(original).get('mcp_servers',{})
        for registration in set(owned):
            current=configured.get(registration)
            if current is not None and current!=self.entry(profile):
                raise ValueError('MCP registration changed outside this client; retained')
            text=remove_table(text,registration)
        if self.config.read_text()!=original:raise ValueError('Configuration changed concurrently')
        self.write(self.config,text)
        if state['active']==name:state['active']=None
        del state['connections'][name];self.save(state)
        return {'disconnected':name,'credential_retained':True,'server_token_not_revoked':True}


def remove_table(text,name):
    parsed=tomllib.loads(text);existing=parsed.get('mcp_servers',{}).get(name)
    if existing is None:return text
    # Reuse the parser-backed table replacement, then remove its canonical table.
    normalized=config_text(text,name,{'url':existing.get('url')})
    suffix='\n[mcp_servers.'+json.dumps(name)+']\nurl = '+json.dumps(existing.get('url'))+'\n'
    if not normalized.endswith(suffix):raise ValueError('Cannot safely remove connection')
    result=normalized[:-len(suffix)]+'\n';expected=json.loads(json.dumps(parsed));del expected['mcp_servers'][name]
    actual=tomllib.loads(result)
    if not expected['mcp_servers']:expected.pop('mcp_servers');actual.pop('mcp_servers',None)
    if actual!=expected:raise ValueError('Cannot safely remove nested connection')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home',type=Path);parser.add_argument('--skill-root',type=Path)
    sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('preflight',help='Print writable roots including missing parent directories; does not install or connect')
    connect=sub.add_parser('connect');connect.add_argument('url');connect.add_argument('--name',default='loom-use');connect.add_argument('--authentication',choices=['auto','token','tailscale'],default='auto')
    for name in ('doctor','update','reconnect'):
        p=sub.add_parser(name);p.add_argument('--name')
    for p in [connect,*[sub.choices[n] for n in ('doctor','update','reconnect')]]:
        p.add_argument('--cwd',type=Path,default=Path.cwd(),help='Existing project directory for Skill refresh; defaults to the shell working directory (not auto-discovered)')
        p.add_argument('--thread-id',default=os.environ.get('CODEX_THREAD_ID'),help='Optional current-chat verification only; defaults to CODEX_THREAD_ID, never stored in MCP registration')
    ssh=sub.add_parser('ssh');ssh.add_argument('operation',choices=['install','info','doctor']);ssh.add_argument('--name')
    connections=sub.add_parser('connections');connections.add_argument('operation',choices=['list','use','disconnect']);connections.add_argument('name',nargs='?')
    a=parser.parse_args()
    if a.action=='preflight':
        print(json.dumps(path_plan(a.home,a.skill_root),indent=2));return 0
    global ERROR_DIRECTORY
    ERROR_DIRECTORY=Path(a.home or os.environ.get('CODEX_HOME',Path.home()/'.codex'))/'loom-use/diagnostics'
    client=Client(a.home,a.skill_root)
    with client.lock():
        if a.action=='connect':
            try:result=client.connect(a.url,a.name,authentication=a.authentication,cwd=a.cwd,thread_id=a.thread_id)
            except (PermissionError,HTTPError) as error:
                if isinstance(error,HTTPError) and error.code not in (401,403):raise
                if isinstance(error,PermissionError) and str(error)!='admin_token_required':raise
                if a.authentication=='tailscale':raise
                if not sys.stdin.isatty():raise PermissionError('Loom Agent Token required: ask an Admin to issue one in Dashboard > Tailscale > Agent Tokens, then rerun this command in your terminal for hidden input; never put it in chat or arguments')
                print('Obtain a token from Dashboard → Tailscale → Agent Tokens (Admin).',file=sys.stderr)
                token=getpass.getpass('Agent token (hidden): ')
                result=client.connect(a.url,a.name,token=token,cwd=a.cwd,thread_id=a.thread_id)
        elif a.action=='ssh':result=client.ssh(a.operation,a.name)
        elif a.action=='update':result=client.update(a.name,a.cwd,a.thread_id)
        elif a.action in ('doctor','reconnect'):result=client.doctor(a.name,a.cwd,a.thread_id,refresh=a.action=='reconnect')
        elif a.operation=='list':
            state=client.load();result={'active':state['active'],'connections':{n:{k:v for k,v in p.items() if k not in ('credential','release_path')} for n,p in state['connections'].items()}}
        elif a.operation=='use':result=client.use(a.name,Path.cwd(),os.environ.get('CODEX_THREAD_ID'))
        else:
            result=client.disconnect(a.name)
    print(json.dumps(result,indent=2))
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        # HTTP bodies and subprocess output may contain secrets: never echo them.
        if isinstance(error,HTTPError):message=f'HTTP {error.code}: check access or token; no credentials changed'
        elif type(error) in (ValueError,PermissionError,KeyError):message=str(error)
        else:message=type(error).__name__+': check network, local paths and permissions'
        incident=diagnostics.record('loom-use','command',error,directory=globals().get('ERROR_DIRECTORY',Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))/'loom-use/diagnostics'),build=(ROOT/'VERSION').read_text().strip())
        print(json.dumps({'status':'incomplete','error':message,'incident_id':incident}),file=sys.stderr);raise SystemExit(1)
