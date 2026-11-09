import json,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'clients'))
import ssh

class SSHTests(unittest.TestCase):
    def setUp(self):
        self.profile={'endpoint':'https://server.example/mcp'}
        self.info={'host':'server.example','port':22,'addresses':['100.64.0.1'],'state':'enabled','username':'loomu_one'}
    def test_same_machine_needs_no_account_even_when_not_enabled(self):
        self.info['state']='not_enabled';self.info.pop('username')
        r=ssh.inspect(self.profile,self.info,{'100.64.0.1'})
        self.assertEqual(r['mode'],'local');self.assertNotIn('argv',r)
    def test_remote_requires_exact_host_and_account(self):
        r=ssh.inspect(self.profile,self.info,set());self.assertEqual(r['mode'],'ssh');self.assertIn('StrictHostKeyChecking=yes',r['argv'])
        for k,v in [('host','evil.example'),('username','root'),('username','loomu_a;echo')]:
            with self.assertRaises(ValueError):ssh.inspect(self.profile,{**self.info,k:v},set())
    def test_revoked_descriptor_does_not_connect(self):
        with patch.object(ssh,'descriptor',return_value={**self.info,'state':'disabled'}),patch.object(ssh,'local_addresses',return_value=set()),patch.object(ssh.subprocess,'run') as run:
            result=ssh.doctor(self.profile)
        self.assertEqual(result['state'],'disabled');run.assert_not_called()
    def test_doctor_checks_actual_remote_username(self):
        with patch.object(ssh,'descriptor',return_value=self.info),patch.object(ssh,'local_addresses',return_value=set()),patch.object(ssh.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='loomu_one\n')) as run:
            self.assertTrue(ssh.doctor(self.profile)['verified']);self.assertEqual(run.call_args.args[0][-1],'id -un')
            run.return_value.stdout='root\n';self.assertFalse(ssh.doctor(self.profile)['verified'])
    def test_local_detection_failure_does_not_invent_local_access(self):
        with patch.object(ssh.subprocess,'run',side_effect=FileNotFoundError):self.assertEqual(ssh.local_addresses(),set())
    def test_optional_skill_update_rolls_back_both_links(self):
        import loom_use
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);c=loom_use.Client(root/'codex',root/'skills');release=c.root/'releases'/'fixture'
            for n in ('loom-use','loom-ssh'):
                (release/'skills'/n).mkdir(parents=True);(release/'skills'/n/'SKILL.md').write_text('fixture')
            c.skill(release);c.skill(release,'loom-ssh')
            self.assertEqual((c.skill_root/'loom-ssh').resolve(),release/'skills/loom-ssh')
            other=c.root/'releases'/'broken';(other/'skills/loom-use').mkdir(parents=True);(other/'skills/loom-use/SKILL.md').write_text('fixture')
            @loom_use.transactional
            def change(client):client.skill(other)
            with self.assertRaises(ValueError):change(c)
            for n in ('loom-use','loom-ssh'):self.assertEqual((c.skill_root/n).resolve(),release/'skills'/n)
