import hashlib,io,json,os,shutil,stat,sys,tempfile,tomllib,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import loom_use as use
import package
from clients import releases,codex_runtime

class ClientTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.client=use.Client(self.root/'codex',self.root/'skills')
  self.client.config.write_text('model="example"\n[mcp_servers.other]\nurl="https://other.test/mcp"\n')
  self.lock=package.build(self.root/'package');self.data=(self.root/'package'/f'loom-use-{self.lock["version"]}.zip').read_bytes()
  self.release=releases.unpack(self.data,self.lock,self.client.root/'releases')
  self.report={'machine_id':'machine-one','manifest':{'client_release':self.lock,'revision':'r1'},'scope':'independent_transport'}
  self.patches=[patch.object(use,'resolve',side_effect=use.endpoint),patch.object(use,'local_identity',return_value={'tagged':False}),
    patch.object(use.releases,'install',return_value=self.release),patch.object(use.codex_runtime,'reconnect',return_value={'status':'pending'})]
  for p in self.patches:p.start();self.addCleanup(p.stop)
 def connect(self,name='loom-use',url='https://one.test',token='fixture-token'):
  with patch.object(self.client,'probe',return_value=self.report):return self.client.connect(url,name,token=token,cwd=self.root)
 def test_connect_reuse_and_doctor_scope(self):
  self.connect();state=self.client.load();secret=state['connections']['loom-use']['credential']
  self.assertEqual(Path(secret).stat().st_mode&0o777,0o600)
  self.assertNotIn('fixture-token',self.client.config.read_text()+self.client.index.read_text())
  with patch.object(self.client,'probe',return_value=self.report) as probe:
   self.client.connect('https://one.test',cwd=self.root)
   self.assertEqual(probe.call_args.args[1],Path(secret))
   result=self.client.doctor(None,self.root)
  self.assertEqual(result['runtime']['status'],'unverified');self.assertFalse(result['client_update_required'])
  self.assertEqual(tomllib.loads(self.client.config.read_text())['mcp_servers']['other']['url'],'https://other.test/mcp')
 def test_switch_preserves_profiles_and_never_forwards_other_token(self):
  self.connect();first=self.client.load()['connections']['loom-use']['credential']
  with patch.object(self.client,'probe',return_value=self.report) as probe:
   self.client.connect('https://two.test','second',cwd=self.root)
   self.assertEqual(len(probe.call_args.args),1)
   self.client.use('second',self.root)
  self.assertEqual(self.client.load()['active'],'second')
  self.assertEqual(len(self.client.load()['connections']),2)
  self.assertEqual(tomllib.loads(self.client.config.read_text())['mcp_servers']['loom-use'],{'url':'https://two.test/mcp'})
  self.assertTrue(Path(first).exists())
 def test_failed_switch_and_failed_skill_leave_config_unchanged(self):
  self.connect();before=self.client.config.read_bytes();index=self.client.index.read_bytes()
  with self.assertRaises(ValueError):self.client.connect('https://two.test',cwd=self.root)
  self.assertEqual(before,self.client.config.read_bytes())
  with patch.object(self.client,'probe',return_value=self.report),patch.object(self.client,'skill',side_effect=ValueError('custom skill')):
   with self.assertRaises(ValueError):self.client.connect('https://two.test','second',token='token2',cwd=self.root)
  self.assertEqual(before,self.client.config.read_bytes());self.assertEqual(index,self.client.index.read_bytes())
 def test_missing_cwd_never_calls_server(self):
  with patch.object(self.client,'probe') as probe:
   with self.assertRaisesRegex(ValueError,'directory'):self.client.connect('https://one.test',cwd=self.root/'missing')
   probe.assert_not_called()
 def test_tagged_requires_admin_token(self):
  with patch.object(use,'local_identity',return_value={'tagged':True}),patch.object(self.client,'probe') as probe:
   with self.assertRaisesRegex(PermissionError,'admin_token_required'):self.client.connect('https://one.test',cwd=self.root)
   probe.assert_not_called()
 def test_legacy_adoption_same_endpoint_only(self):
  old=self.root/'old';old.mkdir(mode=0o700);secret=old/'credential.json';secret.write_text('{"token":"old-token"}');secret.chmod(0o600)
  self.client.config.write_text('[mcp_servers."loom-use"]\nurl="https://one.test/mcp"\nhttp_headers_helper="/usr/bin/python3 '+str(old/'headers.py')+' '+str(secret)+'"\n')
  self.assertEqual(self.client.adopt('loom-use','https://one.test/mcp'),secret)
  self.assertIsNone(self.client.adopt('loom-use','https://two.test/mcp'))
  with patch.object(self.client,'probe',return_value=self.report):self.client.connect('https://one.test',cwd=self.root)
  self.assertEqual(secret.read_text(),'{"token":"old-token"}')
 def test_update_failure_preserves_old_and_success_preserves_secret(self):
  self.connect();before=self.client.config.read_bytes();index=self.client.index.read_bytes()
  new={**self.report,'manifest':{'client_release':{**self.lock,'version':self.lock['version'].rsplit('.',1)[0]+'.'+str(int(self.lock['version'].rsplit('.',1)[1])+1)},'revision':'r2'}}
  with patch.object(self.client,'probe',return_value=new),patch.object(use.releases,'install',side_effect=ValueError('hash')):
   with self.assertRaises(ValueError):self.client.update(None,self.root)
  self.assertEqual(before,self.client.config.read_bytes());self.assertEqual(index,self.client.index.read_bytes())
  with patch.object(self.client,'probe',return_value=new):result=self.client.update(None,self.root)
  self.assertTrue(result['updated'])
  self.assertEqual(json.loads(index)['connections']['loom-use']['credential'],self.client.load()['connections']['loom-use']['credential'])
 def test_release_archive_tamper_traversal_and_pinning(self):
  with self.assertRaises(ValueError):releases.unpack(self.data+b'x',self.lock,self.root/'bad')
  with self.assertRaises(ValueError):releases.validate({**self.lock,'url':'https://untrusted.test/file.zip'})
  (self.release/'INSTALL.md').write_text('tampered')
  with self.assertRaises(ValueError):releases.verify(self.release,self.lock)
  data=io.BytesIO()
  with zipfile.ZipFile(data,'w') as z:z.writestr('../escape','no')
  value=data.getvalue()
  with self.assertRaises(ValueError):releases.unpack(value,{**self.lock,'sha256':hashlib.sha256(value).hexdigest()},self.root/'bad')
 def test_remove_table_preserves_unrelated_and_nested(self):
  text='model="x"\n[mcp_servers."loom-use"]\nurl="https://one/mcp"\n[mcp_servers."loom-use".http_headers]\nX="v"\n[mcp_servers.other]\nurl="https://two/mcp"\n'
  result=tomllib.loads(use.remove_table(text,'loom-use'))
  self.assertEqual(result,{'model':'x','mcp_servers':{'other':{'url':'https://two/mcp'}}})
 def test_endpoint_validation(self):
  for url in ['https://user:password@x','http://remote/mcp','https://x/mcp?secret=abc','file:///tmp/test']:
   with self.assertRaises(ValueError):use.endpoint(url)

 def test_inactive_default_doctor_does_not_confuse_selected_server(self):
  self.connect();self.connect('second','https://two.test','second-token')
  with patch.object(self.client,'probe',return_value=self.report):
   self.client.use('second',self.root)
   result=self.client.doctor('loom-use',self.root)
  self.assertEqual(result['registration'],'inactive_profile')
  self.assertEqual(self.client.load()['active'],'second')
 def test_new_name_can_be_initial_default(self):
  self.connect('second','https://two.test')
  with patch.object(self.client,'probe',return_value=self.report):result=self.client.doctor(None,self.root)
  self.assertEqual(result['registration'],'configured')
 def test_server_replacement_does_not_mutate_connection(self):
  self.connect();before=self.client.index.read_bytes()
  with patch.object(self.client,'probe',return_value={**self.report,'machine_id':'replacement'}):
   with self.assertRaisesRegex(ValueError,'identity'):self.client.update(None,self.root)
  self.assertEqual(before,self.client.index.read_bytes())
 def test_duplicate_and_symlink_archive_members_rejected(self):
  for kind in ('duplicate','symlink'):
   data=io.BytesIO()
   with zipfile.ZipFile(data,'w') as z:
    if kind=='duplicate':
     import warnings
     with warnings.catch_warnings():
      warnings.simplefilter('ignore');z.writestr('same','one');z.writestr('same','two')
    else:
     info=zipfile.ZipInfo('link');info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,'../escape')
   raw=data.getvalue()
   with self.assertRaises(ValueError):releases.unpack(raw,{**self.lock,'sha256':hashlib.sha256(raw).hexdigest()},self.root/kind)
 def test_release_build_is_deterministic(self):
  self.assertEqual(package.build(self.root/'again'),self.lock)

class RuntimeTests(unittest.TestCase):
 def test_missing_cwd_and_no_binary_are_pending(self):
  self.assertEqual(codex_runtime.reconnect('loom-use','/not-existing-loom-directory')['reason'],'project_directory_missing')
  with patch.object(codex_runtime.shutil,'which',return_value=None):self.assertEqual(codex_runtime.reconnect('loom-use','/tmp')['reason'],'codex_not_found')
class CLIContextTests(unittest.TestCase):
 def test_context_defaults_and_overrides_are_verification_arguments(self):
  import contextlib,os,sys
  with tempfile.TemporaryDirectory() as t:
   cwd=Path(t)
   for supplied,expected_thread,expected_cwd,env in [
     ([],None,cwd,{}),
     ([], 'current-thread',cwd,{'CODEX_THREAD_ID':'current-thread'}),
     (['--cwd',str(cwd/'project'),'--thread-id','explicit-thread'],'explicit-thread',cwd/'project',{'CODEX_THREAD_ID':'current-thread'})]:
    with patch.dict(os.environ,env,clear=True),patch.object(sys,'argv',['loom_use.py','connect','https://loom.test/mcp',*supplied]),patch.object(Path,'cwd',return_value=cwd),patch.object(use,'Client') as cls,contextlib.redirect_stdout(io.StringIO()):
     cls.return_value.connect.return_value={}
     self.assertEqual(use.main(),0)
     kwargs=cls.return_value.connect.call_args.kwargs
     self.assertEqual(kwargs['cwd'],expected_cwd);self.assertEqual(kwargs['thread_id'],expected_thread)

if __name__=='__main__':unittest.main()
