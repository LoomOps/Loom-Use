#!/usr/bin/env python3
"""Download a versioned Loom guide bundle; never execute downloaded content."""
import argparse,hashlib,io,json,os,re,stat,tempfile,zipfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,build_opener,HTTPRedirectHandler

class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def cached_files(target):
 paths=list(target.rglob('*'))
 if any(p.is_symlink() or not (p.is_file() or p.is_dir()) for p in paths):raise ValueError('Guide cache contains linked or special paths')
 result={}
 for p in paths:
  if p.is_file() and p!=target/'.verified.json':
   with p.open('rb') as stream:result[str(p.relative_to(target))]=hashlib.file_digest(stream,'sha256').hexdigest()
 return result

def verify_cache(target,revision):
 files=cached_files(target)
 receipt=json.loads((target/'.verified.json').read_text())
 if (not isinstance(receipt,dict) or receipt.get('revision')!=revision or not isinstance(receipt.get('files'),dict)
     or 'manifest.json' not in receipt['files'] or files!=receipt['files']):
  raise ValueError('Guide cache changed; retained without overwrite')

def refresh(url,destination,token,development=False,authentication=None):
 parsed=urlsplit(url)
 if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Use an HTTP(S) Loom base URL without credentials or query')
 if parsed.scheme=='http' and parsed.hostname not in ('localhost','127.0.0.1','::1'):raise ValueError('Remote URLs require HTTPS')
 if authentication not in (None,'tailscale'):raise ValueError('Unknown authentication method')
 if authentication and (token or development):raise ValueError('Choose one authentication method')
 if not token and not development and authentication!='tailscale':raise ValueError('Use an Admin-issued LOOM_TOKEN, --authentication tailscale, or --development for a dev instance')
 base=url.rstrip('/');headers={'Authorization':'Bearer '+token} if token else {}
 opener=build_opener(NoRedirect)
 def get(path):
  with opener.open(Request(base+path,headers=headers),timeout=30) as response:
   data=response.read(8*1024*1024+1)
   if len(data)>8*1024*1024:raise ValueError('Bundle too large')
   return data
 principal=json.loads(get('/api/principal'))
 if authentication=='tailscale' and principal.get('identity',{}).get('provider')!='tailscale':raise ValueError('Verified Tailscale user identity required')
 manifest=json.loads(get('/api/guide'))['manifest']
 server=hashlib.sha256((base+'\0'+hashlib.sha256(token.encode()).hexdigest()+'\0'+json.dumps({k:principal.get(k) for k in ('id','scopes','profile_id')},sort_keys=True)).encode()).hexdigest()[:16]
 revision=manifest['revision']
 if not re.fullmatch('[0-9a-f]{64}',revision):raise ValueError('Invalid server revision')
 parent=Path(destination)/server;target=parent/revision
 if target.is_symlink() or any(p.is_symlink() for p in [parent,*parent.parents]):raise ValueError('Guide cache must not use symlinks')
 if target.exists() and not target.is_dir():raise ValueError('Guide cache target must be a directory')
 if target.is_dir() and (target/'.verified.json').exists():
  verify_cache(target,revision)
  return {'updated':False,'path':str(target),'manifest':manifest}
 data=get('/api/guide/bundle');archive=zipfile.ZipFile(io.BytesIO(data))
 names=archive.namelist()
 if not 1<=len(names)<=4096 or len(names)!=len(set(names)) or sum(i.file_size for i in archive.infolist())>8*1024*1024:raise ValueError('Invalid bundle size or duplicate entries')
 for name in names:
  p=Path(name)
  if p.is_absolute() or '..' in p.parts or '\\' in name or not name or str(p)!=name or name.endswith('/') or p.name=='.verified.json' or stat.S_ISLNK(archive.getinfo(name).external_attr>>16):raise ValueError('Invalid bundle path')
 if json.loads(archive.read('manifest.json'))['revision']!=revision:raise ValueError('Deployment changed during download; retry')
 contents={name:archive.read(name) for name in names}
 hashes={name:hashlib.sha256(content).hexdigest() for name,content in contents.items()}
 receipt=json.dumps({'revision':revision,'files':hashes})+'\n'
 if target.is_dir():
  if cached_files(target)!=hashes:raise ValueError('Guide cache changed; retained without overwrite')
  # Upgrade a pre-receipt cache only after comparison with the server bundle.
  with (target/'.verified.json').open('x') as out:out.write(receipt)
  (target/'.verified.json').chmod(0o600)
  return {'updated':False,'path':str(target),'manifest':manifest}
 parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(dir=parent,prefix='.download-') as temp:
  staging=Path(temp)/'bundle';staging.mkdir()
  for name,content in contents.items():
   file=staging/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(content);file.chmod(0o600)
  (staging/'.verified.json').write_text(receipt);(staging/'.verified.json').chmod(0o600)
  staging.rename(target)
 return {'updated':True,'path':str(target),'manifest':manifest}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('url');p.add_argument('--directory',type=Path,default=Path.home()/'.cache/loom/guides');p.add_argument('--development',action='store_true');p.add_argument('--authentication',choices=['tailscale']);a=p.parse_args()
 try:print(json.dumps(refresh(a.url,a.directory,os.getenv('LOOM_TOKEN',''),a.development,a.authentication),indent=2))
 except Exception as error:p.exit(1,type(error).__name__+': guide refresh failed; check endpoint, authentication and bundle integrity.\n')
