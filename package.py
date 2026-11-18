"""Build a deterministic, credential-free source release."""
import argparse,hashlib,io,json,os,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def publish(path,data):
 path=Path(path)
 if path.is_file() and path.read_bytes()==data:return False
 fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
  os.chmod(name,0o644);os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)
 return True

def build(output):
 output=Path(output);output.mkdir(parents=True,exist_ok=True)
 version=(ROOT/'VERSION').read_text().strip();target=output/f'loom-use-{version}.zip'
 files=[ROOT/n for n in ('VERSION','README.md','INSTALL.md','AGENTS.md','LICENSE','THIRD_PARTY_NOTICES.md','loom_use.py','refresh.py')]
 for directory in ('clients','skills','docs'):
  files += [p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
 buffer=io.BytesIO()
 with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(files):
   info=zipfile.ZipInfo(str(p.relative_to(ROOT)),date_time=(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
   z.writestr(info,p.read_bytes())
 publish(target,buffer.getvalue())
 lock={'version':version,'url':f'https://github.com/LoomOps/Loom-Use/releases/download/v{version}/{target.name}','sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
 publish(output/'client-release.json',(json.dumps(lock,indent=2)+'\n').encode());return lock
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.output),indent=2))
