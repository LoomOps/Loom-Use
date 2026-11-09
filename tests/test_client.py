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

 def test_explicit_tailscale_drops_saved_header_but_preserves_secret(self):
  self.connect();secret=Path(self.client.load()['connections']['loom-use']['credential'])
  with patch.object(self.client,'probe',return_value=self.report) as probe:
   self.client.connect('https://one.test',authentication='tailscale',cwd=self.root)
   self.assertEqual(probe.call_args.args,('https://one.test/mcp',))
  self.assertTrue(secret.exists())
  self.assertEqual(tomllib.loads(self.client.config.read_text())['mcp_servers']['loom-use'],{'url':'https://one.test/mcp'})
  with self.assertRaisesRegex(ValueError,'must not carry'):
   self.client.connect('https://one.test',authentication='tailscale',token='fixture',cwd=self.root)

 def test_connect_rejects_replaced_server_before_installing(self):
  self.connect();before=self.client.index.read_bytes()
  with patch.object(self.client,'probe',return_value={**self.report,'machine_id':'replacement'}),patch.object(use.releases,'install') as install:
   with self.assertRaisesRegex(ValueError,'identity'):self.client.connect('https://one.test',cwd=self.root)
   install.assert_not_called()
  self.assertEqual(before,self.client.index.read_bytes())

 def test_rollback_preserves_concurrent_config_before_and_after_own_write(self):
  self.connect()
  concurrent='model="another-writer"\n'
  with patch.object(self.client,'probe',return_value=self.report):
   def raced(*args,**kwargs):
    self.client.config.write_text(concurrent)
    raise ValueError('Configuration changed concurrently')
   with patch.object(self.client,'register',side_effect=raced):
    with self.assertRaises(ValueError):self.client.connect('https://one.test',cwd=self.root)
   self.assertEqual(self.client.config.read_text(),concurrent)
   with patch.object(self.client,'skill',side_effect=raced):
    with self.assertRaises(ValueError):self.client.connect('https://one.test',cwd=self.root)
   self.assertEqual(self.client.config.read_text(),concurrent)

 def test_failed_connect_preserves_concurrently_replaced_skill_link(self):
  self.connect();link=self.client.skill_root/'loom-use'
  def raced(state):
   link.unlink();link.symlink_to(self.root/'external-skill')
   raise ValueError('later failure')
  with patch.object(self.client,'probe',return_value=self.report),patch.object(self.client,'save',side_effect=raced):
   with self.assertRaises(ValueError):self.client.connect('https://one.test',cwd=self.root)
  self.assertEqual(os.readlink(link),str(self.root/'external-skill'))

 def test_disconnect_and_switch_preserve_foreign_registrations(self):
  self.connect();self.connect('second','https://two.test','second-token')
  foreign=self.client.config.read_text().replace('https://one.test/mcp','https://foreign.test/mcp')
  self.client.config.write_text(foreign);index=self.client.index.read_bytes()
  with self.assertRaisesRegex(ValueError,'outside this client'):self.client.disconnect('loom-use')
  with patch.object(self.client,'probe',return_value=self.report):
   with self.assertRaisesRegex(ValueError,'outside this client'):self.client.use('second',self.root)
  self.assertEqual(self.client.config.read_text(),foreign);self.assertEqual(self.client.index.read_bytes(),index)
  foreign=foreign.replace('https://two.test/mcp','https://another.test/mcp');self.client.config.write_text(foreign)
  with self.assertRaisesRegex(ValueError,'outside this client'):self.client.disconnect('second')
  self.assertEqual(self.client.config.read_text(),foreign);self.assertEqual(self.client.index.read_bytes(),index)

 def test_disconnect_keeps_credentials_and_other_connections(self):
  self.connect();self.connect('second','https://two.test','second-token')
  token=Path(self.client.load()['connections']['loom-use']['credential'])
  self.assertTrue(self.client.disconnect('loom-use')['credential_retained'])
  self.assertTrue(token.exists())
  self.assertIn('second',self.client.load()['connections'])
  config=tomllib.loads(self.client.config.read_text())
  self.assertNotIn('loom-use',config['mcp_servers']);self.assertIn('other',config['mcp_servers'])

 def test_same_endpoint_external_auth_changes_are_preserved(self):
  self.connect();self.connect('second','https://two.test','second-token')
  original=self.client.config.read_text()
  foreign=original.replace('url = "https://one.test/mcp"','url = "https://one.test/mcp"\nstartup_timeout_sec = 90')
  self.assertNotEqual(original,foreign);self.client.config.write_text(foreign)
  before=self.client.index.read_bytes()
  for action in (lambda:self.connect(),lambda:self.client.update(None,self.root),lambda:self.client.use('second',self.root)):
   with patch.object(self.client,'probe',return_value=self.report),self.assertRaisesRegex(ValueError,'outside this client'):action()
   self.assertEqual(self.client.config.read_text(),foreign);self.assertEqual(self.client.index.read_bytes(),before)

 def test_cache_rejects_extra_source_symlink_parents_and_noncanonical_archive_paths(self):
  extra=self.release/'clients/extra.py';extra.write_text('raise RuntimeError("untrusted")')
  with self.assertRaisesRegex(ValueError,'file set'):releases.verify(self.release,self.lock)
  extra.unlink();cache=self.release/'clients/__pycache__';cache.mkdir();(cache/'fixture.pyc').write_bytes(b'cache')
  releases.verify(self.release,self.lock)
  clients=self.release/'clients';outside=self.root/'moved-clients';clients.rename(outside);clients.symlink_to(outside,target_is_directory=True)
  with self.assertRaisesRegex(ValueError,'symlink'):releases.verify(self.release,self.lock)
  for name in ('./VERSION','clients//headers.py','clients/./headers.py'):
   data=io.BytesIO()
   with zipfile.ZipFile(data,'w') as z:z.writestr(name,'ambiguous')
   raw=data.getvalue()
   with self.assertRaisesRegex(ValueError,'Unsafe'):releases.unpack(raw,{**self.lock,'sha256':hashlib.sha256(raw).hexdigest()},self.root/'bad-canonical')

 def test_legacy_configure_keeps_old_credential_on_config_race(self):
  import setup as primitive
  folder=self.root/'legacy';folder.mkdir(mode=0o700);secret=folder/'credential.json';secret.write_text('{"token":"old"}\n');secret.chmod(0o600)
  foreign='model="foreign writer"\n'
  def verify(*args):self.client.config.write_text(foreign);return {'scope':'independent_transport'}
  with patch.object(primitive,'verify',side_effect=verify):
   with self.assertRaisesRegex(ValueError,'configuration changed'):primitive.configure(folder,self.client.config,'legacy','https://one.test/mcp','new')
  self.assertEqual(secret.read_text(),'{"token":"old"}\n');self.assertEqual(self.client.config.read_text(),foreign)
  self.assertFalse((folder/'headers.py').exists())
  original=primitive.atomic_private;written=[]
  def raced(path,content):
   original(path,content)
   if path.name=='client.json' and not written:written.append(True);self.client.config.write_text('model="later writer"\n')
  with patch.object(primitive,'verify',return_value={'scope':'independent_transport'}),patch.object(primitive,'atomic_private',side_effect=raced):
   with self.assertRaisesRegex(ValueError,'configuration changed'):primitive.configure(folder,self.client.config,'legacy','https://one.test/mcp','new')
  self.assertEqual(secret.read_text(),'{"token":"old"}\n');self.assertEqual(self.client.config.read_text(),'model="later writer"\n')
  self.assertFalse((folder/'headers.py').exists())

 def test_incomplete_local_tailscale_identity_does_not_crash(self):
  from types import SimpleNamespace
  for data in ({'Self':None},[],{'Self':'invalid'}):
   with patch.object(use.subprocess,'run',return_value=SimpleNamespace(stdout=json.dumps(data))):
    result=use.local_identity();self.assertIn(result['tagged'],(False,None))

class RuntimeTests(unittest.TestCase):
 def test_missing_cwd_and_missing_control_are_pending(self):
  self.assertEqual(codex_runtime.reconnect('loom-use','/not-existing-loom-directory')['reason'],'project_directory_missing')
  with patch.object(codex_runtime,'discover_socket',side_effect=codex_runtime.ControlPathError('control_socket_missing')):self.assertEqual(codex_runtime.reconnect('loom-use','/tmp')['reason'],'control_socket_missing')
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

class PreflightTests(unittest.TestCase):
 def test_missing_parent_is_part_of_grant_plan_without_writes(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);target=root/'.agents/skills'
   plan=use.path_plan(root/'.codex',target)
   self.assertEqual(plan['paths'][1]['write_scope'],str(root/'.agents'))
   self.assertFalse(target.parent.exists())
 def test_failed_skill_permission_does_not_contact_server_or_change_config(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);client=use.Client(root/'codex',root/'new-parent/skills')
   client.config.write_text('model="kept"\n')
   with patch.object(use.tempfile,'TemporaryFile',side_effect=PermissionError('denied')),patch.object(client,'probe') as probe:
    with self.assertRaisesRegex(PermissionError,'grant access'):client.connect('https://example.test',cwd=root)
   probe.assert_not_called();self.assertEqual(client.config.read_text(),'model="kept"\n')
