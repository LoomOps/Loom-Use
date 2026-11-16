"""Metadata-only File handoff with an explicit, read-only local/SSH probe."""
import ipaddress,json,re,shlex,subprocess
from pathlib import PurePosixPath
import ssh


def relative(value):
    if (not isinstance(value,str) or not value or len(value)>4096
            or any(ord(c)<32 or ord(c)==127 for c in value)
            or value.startswith('/') or any(p in ('','.','..') for p in value.split('/'))):
        raise ValueError('Use a nonescaping relative file/member path')
    return value


def absolute(value):
    if (not isinstance(value,str) or not value.startswith('/') or value.startswith('//') or value=='/'
            or str(PurePosixPath(value))!=value or '..' in PurePosixPath(value).parts
            or any(ord(c)<32 or ord(c)==127 for c in value)):
        raise ValueError('Use a normalized absolute host path')
    return value


# This fixed script receives data as JSON, never executable server-provided code.
# Opening each component relative to directory FDs also rejects escaping symlinks.
PROBE = r'''
import errno,hashlib,importlib.util,json,os,pwd,stat,sys
p=json.loads(sys.argv[1]);result={'verified':False,'storage_identity_verified':False,'content_verification':'not_checked','member':{'path':p['member'],'state':'not_inspected'} if p['member'] else None}
fds=[]
def opened(root,ref):
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);fds.append(fd)
    for part in ref.split('/')[:-1]:
        fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);fds.append(fd)
    return os.open(ref.split('/')[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
def stamp(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
try:
    user=pwd.getpwuid(os.getuid()).pw_name;result['user']=user
    if p['username'] and user!=p['username']:raise ValueError('unexpected_ssh_account')
    root=p['root']
    if os.path.realpath(root)!=root:raise ValueError('redirected_storage_root')
    with os.fdopen(opened(root,'.loom-storage.json'),'rb') as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):raise ValueError('storage_marker_not_regular')
        marker_bytes=f.read(65537)
    if len(marker_bytes)>65536:raise ValueError('storage_marker_too_large')
    try:marker=json.loads(marker_bytes)
    except (ValueError,UnicodeError):raise ValueError('invalid_storage_marker') from None
    if marker!={'storage_id':p['storage_id']}:raise ValueError('storage_identity_changed')
    result['storage_identity_verified']=True
    with os.fdopen(opened(root,p['ref']),'rb') as f:
        before=os.fstat(f.fileno())
        if not stat.S_ISREG(before.st_mode):raise ValueError('not_a_regular_file')
        result['actual_size']=before.st_size
        if before.st_size!=p['size']:raise ValueError('size_mismatch')
        f.read(1);result['readable']=True
        if p['verify']:
            f.seek(0);h=hashlib.sha256()
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
            digest=h.hexdigest();result['actual_sha256']=digest
            if digest!=p['sha256']:raise ValueError('hash_mismatch')
            result['content_verification']='sha256_matched'
        if stamp(os.fstat(f.fileno()))!=stamp(before):raise ValueError('file_changed_during_probe')
    result['python']={'executable':sys.executable,'prefix':sys.prefix,'packages':{m:importlib.util.find_spec(m) is not None for m in ('numpy','h5py','torch')}}
    result.update(verified=True,state='readable')
except (OSError,ValueError) as e:
    code=('permission_denied' if e.errno in (errno.EACCES,errno.EPERM) else 'missing' if e.errno==errno.ENOENT else 'symlink_or_nondirectory' if e.errno in (errno.ELOOP,errno.ENOTDIR) else 'filesystem_error') if isinstance(e,OSError) else str(e)
    result.update(verified=False,state=code)
    if code=='hash_mismatch':result['content_verification']='sha256_mismatch'
    elif code=='file_changed_during_probe':result['content_verification']='invalidated'
finally:
    for fd in reversed(fds):os.close(fd)
print(json.dumps(result))
'''


def probe_location(access,location,file,python,member,verify):
    payload={'root':location['root'],'storage_id':location['locator']['storage_id'],'ref':location['locator']['ref'],
             'size':file['size'],'sha256':file['sha256'],'username':access.get('username') if access['mode']=='ssh' else None,'member':member,'verify':verify}
    command=[python,'-I','-c',PROBE,json.dumps(payload)]
    if access['mode']=='ssh':command=[access['argv'][0],'-o','BatchMode=yes',*access['argv'][1:],shlex.join(command)]
    try:
        run=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60 if verify else 20)
    except subprocess.TimeoutExpired:return {'verified':False,'state':'timeout','content_verification':'not_checked'}
    except OSError:return {'verified':False,'state':'interpreter_or_ssh_unavailable','content_verification':'not_checked'}
    if run.returncode:return {'verified':False,'state':'ssh_or_interpreter_failed' if access['mode']=='ssh' else 'interpreter_failed','exit_code':run.returncode,'content_verification':'not_checked'}
    if len(run.stdout)>65536:raise ValueError('File probe response exceeds its bound')
    try:value=json.loads(run.stdout)
    except ValueError:return {'verified':False,'state':'invalid_probe_response','content_verification':'not_checked'}
    if not isinstance(value,dict) or type(value.get('verified')) is not bool:raise ValueError('Invalid file probe response')
    return value


def manual_route(target,port):
    if type(port) is not int or not 1<=port<=65535:raise ValueError('Invalid SSH port')
    if not isinstance(target,str) or target.count('@')!=1:raise ValueError('Use an existing SSH route as USER@HOST')
    user,host=target.split('@')
    if not re.fullmatch('[A-Za-z_][A-Za-z0-9_.-]{0,63}',user):raise ValueError('Invalid SSH username')
    try:ipaddress.ip_address(host);valid=True
    except ValueError:valid=bool(re.fullmatch('[A-Za-z0-9][A-Za-z0-9.-]{0,252}',host))
    if not valid or any(c.isspace() for c in host) or ('%' in host and not re.fullmatch('[A-Za-z0-9_.-]+',host.split('%',1)[1])):raise ValueError('Invalid SSH host')
    return {'mode':'ssh','state':'enabled','username':user,'host':host,'port':port,'authorization':'existing_user_supplied_route',
            'host_binding':'unverified','argv':['ssh','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','-p',str(port),target]}


def resolve(profile,file_id,*,copy=None,python=None,member=None,probe=False,verify=False,ssh_target=None,ssh_port=22):
    if not isinstance(file_id,str) or not re.fullmatch(r'[1-9][0-9]{0,38}',file_id) or int(file_id)>=2**128:
        raise ValueError('Use a canonical 128-bit decimal File ID string')
    if verify and not probe:raise ValueError('--verify requires --probe; it reads the whole selected file')
    python=absolute(python) if python else 'python3'
    member=relative(member) if member is not None else None
    with ssh.metadata(profile) as call:
        status=call('system','status')
        if not isinstance(status,dict) or not profile.get('machine_id') or status.get('machine_id')!=profile['machine_id']:raise ValueError('Server identity changed')
        info=call('system','ssh')
        file=call('results','get_file',{'file_item_id':file_id})
    if (not isinstance(file,dict) or file.get('item_id')!=file_id
            or (file.get('size') is not None and (type(file['size']) is not int or file['size']<0))
            or (file.get('sha256') is not None and (not isinstance(file['sha256'],str) or not re.fullmatch('[a-f0-9]{64}',file['sha256'])))):
        raise ValueError('Invalid registered File identity, size or SHA-256')
    copies=file.get('copies',[])
    if not isinstance(copies,list) or len(copies)>200:raise ValueError('Invalid File copy list')
    if copy is not None and (type(copy) is not int or not 0<=copy<len(copies)):raise ValueError('Copy index is outside the returned copy list')
    if not isinstance(info,dict):raise ValueError('Invalid SSH connection metadata')
    stores=status.get('data_stores') or {};roots=info.get('data_paths') or {}
    if not isinstance(stores,dict) or not isinstance(roots,dict):raise ValueError('Invalid storage path metadata')
    access=ssh.inspect(profile,info=info)
    if ssh_target is not None:
        if access['mode']=='local':raise ValueError('Same-host access uses the current OS account; omit --ssh-target')
        access=manual_route(ssh_target,ssh_port)
    elif ssh_port!=22:raise ValueError('--ssh-port requires --ssh-target')
    locations=[]
    for i,c in enumerate(copies):
        loc={'copy_index':i,'state':'unsupported_copy','locator':c}
        if not isinstance(c,dict):raise ValueError('Invalid File copy')
        if c.get('type')=='storage':
            if not isinstance(c.get('storage_id'),str) or not c['storage_id']:raise ValueError('Missing File storage identity')
            if c.get('machine_id')!=status['machine_id']:loc['state']='another_machine'
            else:
                slots=[k for k,s in stores.items() if isinstance(s,dict) and s.get('storage_id')==c.get('storage_id')]
                if len(slots)>1:raise ValueError('Storage ID has ambiguous selectors')
                if not slots or not roots.get(slots[0]):loc['state']='storage_mapping_unavailable'
                else:
                    root=absolute(roots[slots[0]]);ref=relative(c.get('ref'))
                    loc.update(state='mapped',storage=slots[0],root=root,path=str(PurePosixPath(root)/ref))
        locations.append(loc)
    mapped=[l for l in locations if l['state']=='mapped']
    selected=locations[copy] if copy is not None else next((l for l in mapped if l['locator'].get('status')=='available'),next(iter(mapped),None))
    enabled=access['mode']=='local' or access.get('state')=='enabled'
    state=selected['state'] if selected and selected['state']!='mapped' else 'no_mapped_copy' if selected is None else 'resolved' if enabled else 'ssh_access_required'
    if state=='resolved' and (file.get('size') is None or file.get('sha256') is None):state='content_identity_unrecorded'
    result={'schema':'loom-file-access/v1','state':state,'connection':{'endpoint':profile['endpoint'],'machine_id':status['machine_id']},
            'file':{k:file.get(k) for k in ('item_id','revision_id','owner_revision_id','parent_item_id','label','path','size','sha256','source_sha256')},
            'access':access,'locations':locations,'selected_copy':selected,'archive_member':{'path':member,'state':'not_inspected'} if member else None,
            'analysis_python':{'command':python,'origin':'explicit' if python!='python3' else 'host_default','verified':False},
            'probe':{'state':'not_run','verified':False,'content_verification':'not_checked'}}
    if probe:
        if state!='resolved':result['probe']['state']=state
        else:
            result['probe']=probe_location(access,selected,file,python,member,verify)
            result['analysis_python']['verified']='python' in result['probe']
    return result
