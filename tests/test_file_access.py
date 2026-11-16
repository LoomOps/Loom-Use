import contextlib,copy,hashlib,json,os,pwd,shlex,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'clients'))
import file_access as access
import ssh

class FileAccessTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.store=self.root/'data';self.store.mkdir();(self.store/'.loom-storage.json').write_text('{"storage_id":"store-one"}')
        self.content=b'{"count":4,"empty":0}\n';(self.store/'manifest.json').write_bytes(self.content)
        self.file_id='18446744073709551619'
        self.profile={'endpoint':'https://science.example/mcp','machine_id':'machine-one'}
        self.status={'machine_id':'machine-one','data_stores':{'data/0':{'storage_id':'store-one','mode':'rw'}}}
        self.info={'host':'science.example','addresses':['100.64.0.1'],'data_paths':{'data/0':str(self.store)},'state':'not_enabled'}
        self.file={'item_id':self.file_id,'revision_id':'18446744073709551620','size':len(self.content),'sha256':hashlib.sha256(self.content).hexdigest(),'label':'manifest.json',
                   'copies':[{'type':'storage','machine_id':'machine-one','storage_id':'store-one','ref':'manifest.json','status':'available'}]}
        self.calls=[]
        @contextlib.contextmanager
        def metadata(profile):
            self.assertEqual(profile,self.profile)
            def call(group,action,args=None):
                self.calls.append((group,action,args));return copy.deepcopy({('system','status'):self.status,('system','ssh'):self.info,('results','get_file'):self.file}[group,action])
            yield call
        for p in [patch.object(ssh,'metadata',side_effect=metadata),patch.object(ssh,'local_addresses',return_value={'100.64.0.1'})]:p.start();self.addCleanup(p.stop)

    def test_resolve_uses_only_metadata_and_retains_exact_file_and_local_paths(self):
        with patch.object(access.subprocess,'run') as run:
            r=access.resolve(self.profile,self.file_id)
        run.assert_not_called()
        self.assertEqual(r['state'],'resolved');self.assertEqual(r['file']['item_id'],self.file_id)
        self.assertEqual(r['selected_copy']['path'],str(self.store/'manifest.json'))
        self.assertEqual(r['access']['data_paths'],self.info['data_paths']);self.assertEqual(r['access']['ssh_grant_state'],'not_enabled')
        self.assertFalse(r['probe']['verified']);self.assertEqual([a for g,a,args in self.calls],['status','ssh','get_file'])

    def test_local_probe_reads_file_and_explicit_verify_hashes_without_changing_it(self):
        before=(self.store/'manifest.json').stat()
        r=access.resolve(self.profile,self.file_id,probe=True,python=sys.executable)
        self.assertTrue(r['probe']['verified']);self.assertEqual(r['probe']['content_verification'],'not_checked')
        r=access.resolve(self.profile,self.file_id,probe=True,verify=True,python=sys.executable)
        self.assertTrue(r['probe']['verified']);self.assertEqual(r['probe']['actual_sha256'],self.file['sha256'])
        self.assertEqual(r['probe']['python']['executable'],sys.executable)
        self.assertEqual((self.store/'manifest.json').read_bytes(),self.content)
        self.assertEqual((self.store/'manifest.json').stat().st_mtime_ns,before.st_mtime_ns)
        self.assertEqual(sorted(p.name for p in self.store.iterdir()),['.loom-storage.json','manifest.json'])

    def test_changed_same_size_content_missing_file_and_marker_are_distinct(self):
        (self.store/'manifest.json').write_bytes(b'x'*len(self.content))
        r=access.resolve(self.profile,self.file_id,probe=True,verify=True)
        self.assertEqual(r['probe']['state'],'hash_mismatch');self.assertFalse(r['probe']['verified'])
        (self.store/'manifest.json').unlink()
        self.assertEqual(access.resolve(self.profile,self.file_id,probe=True)['probe']['state'],'missing')
        (self.store/'.loom-storage.json').write_text('{"storage_id":"other"}')
        self.assertEqual(access.resolve(self.profile,self.file_id,probe=True)['probe']['state'],'storage_identity_changed')

    def test_size_mismatch_and_oversized_marker_are_not_accepted(self):
        (self.store/'manifest.json').write_text('different size')
        self.assertEqual(access.resolve(self.profile,self.file_id,probe=True)['probe']['state'],'size_mismatch')
        (self.store/'.loom-storage.json').write_bytes(b'{"storage_id":"store-one"}'+b' '*65536)
        self.assertEqual(access.resolve(self.profile,self.file_id,probe=True)['probe']['state'],'storage_marker_too_large')

    def test_symlink_file_and_redirected_root_never_read_outside_store(self):
        (self.store/'manifest.json').unlink();(self.root/'outside').write_text('secret')
        (self.store/'manifest.json').symlink_to(self.root/'outside')
        r=access.resolve(self.profile,self.file_id,probe=True)
        self.assertEqual(r['probe']['state'],'symlink_or_nondirectory');self.assertFalse(r['probe']['verified'])
        alias=self.root/'alias';alias.symlink_to(self.store);self.info['data_paths']['data/0']=str(alias)
        self.assertEqual(access.resolve(self.profile,self.file_id,probe=True)['probe']['state'],'redirected_storage_root')

    def test_invalid_and_special_storage_markers_are_not_interpreter_failures(self):
        marker=self.store/'.loom-storage.json'
        for value in (b'not JSON',b'\xff'):
            marker.write_bytes(value)
            self.assertEqual(access.resolve(self.profile,self.file_id,probe=True)['probe']['state'],'invalid_storage_marker')
        marker.unlink();os.mkfifo(marker)
        self.assertEqual(access.resolve(self.profile,self.file_id,probe=True)['probe']['state'],'storage_marker_not_regular')

    def test_actual_permission_denial_is_not_misreported_as_a_missing_file(self):
        path=self.store/'manifest.json';path.chmod(0)
        real_run=subprocess.run
        def unprivileged(argv,**kwargs):
            if os.geteuid()==0:kwargs['preexec_fn']=lambda:os.setuid(65534)
            return real_run(argv,**kwargs)
        try:
            with patch.object(access.subprocess,'run',side_effect=unprivileged):r=access.resolve(self.profile,self.file_id,probe=True)
        finally:path.chmod(0o600)
        self.assertEqual(r['probe']['state'],'permission_denied');self.assertFalse(r['probe']['verified'])

    def test_foreign_and_unsupported_copies_do_not_select_another_server(self):
        first=copy.deepcopy(self.file['copies'][0]);first['machine_id']='foreign-machine'
        self.file['copies'].insert(0,first)
        r=access.resolve(self.profile,self.file_id);self.assertEqual(r['selected_copy']['copy_index'],1)
        r=access.resolve(self.profile,self.file_id,copy=0,probe=True)
        self.assertEqual(r['state'],'another_machine');self.assertFalse(r['probe']['verified'])
        self.file['copies']=[{'type':'components','path':'private/source.rs'}]
        r=access.resolve(self.profile,self.file_id,probe=True);self.assertEqual(r['state'],'no_mapped_copy')

    def test_missing_remote_grant_reports_paths_without_connecting_or_creating_accounts(self):
        with patch.object(ssh,'local_addresses',return_value=set()),patch.object(access.subprocess,'run') as run:
            r=access.resolve(self.profile,self.file_id,probe=True)
        self.assertEqual(r['state'],'ssh_access_required');self.assertIn('path',r['selected_copy']);run.assert_not_called()

    def test_unmeasured_registered_file_is_retained_without_inventing_identity_or_probing(self):
        self.file['size']=None;self.file['sha256']=None
        with patch.object(access.subprocess,'run') as run:
            result=access.resolve(self.profile,self.file_id,probe=True,verify=True)
        run.assert_not_called()
        self.assertEqual(result['state'],'content_identity_unrecorded')
        self.assertEqual(result['selected_copy']['path'],str(self.store/'manifest.json'))
        self.assertIsNone(result['file']['sha256']);self.assertFalse(result['probe']['verified'])

    def test_selected_machine_file_identity_and_storage_mapping_are_checked(self):
        self.status['machine_id']='changed'
        with self.assertRaisesRegex(ValueError,'identity'):access.resolve(self.profile,self.file_id)
        self.status['machine_id']='machine-one';self.file['item_id']='1'
        with self.assertRaisesRegex(ValueError,'File identity'):access.resolve(self.profile,self.file_id)
        self.file['item_id']=self.file_id;self.status['data_stores']['data/1']={'storage_id':'store-one'}
        with self.assertRaisesRegex(ValueError,'ambiguous'):access.resolve(self.profile,self.file_id)
        del self.status['data_stores']['data/1'];self.info['data_paths']={}
        self.assertEqual(access.resolve(self.profile,self.file_id,copy=0)['state'],'storage_mapping_unavailable')

    def test_member_hint_does_not_claim_inspection_or_extract_files(self):
        r=access.resolve(self.profile,self.file_id,member='labels/one.json',probe=True)
        self.assertEqual(r['archive_member'],{'path':'labels/one.json','state':'not_inspected'})
        self.assertEqual(r['probe']['member']['state'],'not_inspected')
        self.assertFalse((self.store/'labels').exists())
        for member in ['/absolute','../escape','dir/../escape','double//slash','line\nbreak']:
            with self.assertRaises(ValueError):access.resolve(self.profile,self.file_id,member=member)

    def test_invalid_ids_paths_and_flags_fail_before_execution(self):
        for ident in [1,'01','0',str(2**128),'abc']:
            with self.assertRaises(ValueError):access.resolve(self.profile,ident)
        for ref in ['../escape','/absolute','a/./b','a//b','x\x00']:
            self.file['copies'][0]['ref']=ref
            with self.assertRaises(ValueError):access.resolve(self.profile,self.file_id)
        with self.assertRaises(ValueError):access.resolve(self.profile,self.file_id,verify=True)
        with self.assertRaises(ValueError):access.resolve(self.profile,self.file_id,copy=10)
        with self.assertRaises(ValueError):access.resolve(self.profile,self.file_id,python='python3;echo bad')

    def test_ssh_command_quotes_untrusted_file_names_and_checks_real_account(self):
        # Exercise a real POSIX remote shell boundary using a synthetic SSH transport.
        sentinel=self.root/'injected'
        # Use a filename without slashes; the embedded command still attempts a write.
        ref="report'; touch injected; echo '.json";(self.store/ref).write_bytes(self.content);self.file['copies'][0]['ref']=ref
        user=pwd.getpwuid(os.getuid()).pw_name;real_run=subprocess.run;commands=[]
        def ssh_run(argv,**kwargs):
            commands.append(argv)
            return real_run(['/bin/sh','-c',argv[-1]],cwd=self.root,**kwargs)
        with patch.object(ssh,'local_addresses',return_value=set()),patch.object(access.subprocess,'run',side_effect=ssh_run):
            r=access.resolve(self.profile,self.file_id,ssh_target=user+'@lan.example',ssh_port=9022,probe=True,verify=True,python=sys.executable)
        self.assertTrue(r['probe']['verified']);self.assertFalse(sentinel.exists());self.assertIn('StrictHostKeyChecking=yes',commands[0]);self.assertIn('BatchMode=yes',commands[0])
        self.assertIn('9022',commands[0]);self.assertNotIn('credential',json.dumps(commands))
        with patch.object(ssh,'local_addresses',return_value=set()),patch.object(access.subprocess,'run',side_effect=ssh_run):
            r=access.resolve(self.profile,self.file_id,ssh_target='different_user@lan.example',probe=True)
        self.assertEqual(r['probe']['state'],'unexpected_ssh_account')

    def test_probe_network_failure_and_timeout_are_not_read_success(self):
        self.info.update(state='enabled',username='loomu_reader',port=22)
        with patch.object(ssh,'local_addresses',return_value=set()),patch.object(access.subprocess,'run',side_effect=subprocess.TimeoutExpired('ssh',20)):
            r=access.resolve(self.profile,self.file_id,probe=True)
        self.assertFalse(r['probe']['verified']);self.assertEqual(r['probe']['state'],'timeout')
        with self.assertRaises(ValueError):access.manual_route('user@host;echo',22)
        with self.assertRaises(ValueError):access.manual_route('user@host',0)

    def test_client_resolve_keeps_active_connection_config_and_credentials_unchanged(self):
        import loom_use
        client=loom_use.Client(self.root/'client',self.root/'skills')
        state={'schema':1,'active':'other','connections':{'other':{'endpoint':'https://other/mcp'},'science':self.profile}}
        client.save(state);before=client.index.read_bytes()
        result=client.ssh('resolve','science',file_id=self.file_id)
        self.assertEqual(result['connection']['name'],'science');self.assertEqual(client.index.read_bytes(),before)
        self.assertFalse(client.config.exists());self.assertFalse((self.root/'skills').exists())

    def test_cli_resolve_passes_only_requested_read_options_to_the_named_profile(self):
        import contextlib,io,loom_use
        argv=['loom_use.py','ssh','resolve',self.file_id,'--name','science','--probe','--verify','--python',sys.executable,'--member','labels/one.json','--copy','0']
        with patch.object(sys,'argv',argv),patch.object(loom_use,'Client') as cls,contextlib.redirect_stdout(io.StringIO()):
            cls.return_value.ssh.return_value={};self.assertEqual(loom_use.main(),0)
        cls.return_value.ssh.assert_called_once_with('resolve','science',file_id=self.file_id,copy=0,python=sys.executable,member='labels/one.json',probe=True,verify=True,ssh_target=None,ssh_port=22)
        for args in [['ssh','resolve'],['ssh','info','--probe'],['ssh','resolve',self.file_id,'--verify']]:
            with patch.object(sys,'argv',['loom_use.py',*args]),patch.object(loom_use,'Client') as cls,contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):loom_use.main()
            cls.assert_not_called()

if __name__=='__main__':unittest.main()
