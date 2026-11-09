import email.message, io, json, sys, tempfile, unittest
import os,subprocess,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'clients'))
from stdio import OpsTransport
from headers import read_token

class TransportTests(unittest.TestCase):
 def test_legacy_guide_cache_refuses_aliases_and_symlink_reuse(self):
  import refresh
  from types import SimpleNamespace
  revision='a'*64
  def bundle(name):
   stream=io.BytesIO()
   with zipfile.ZipFile(stream,'w') as z:z.writestr('manifest.json',json.dumps({'revision':revision}));z.writestr(name,'guide')
   return stream.getvalue()
  data=bundle('entry.md')
  def response(req,**kwargs):
   payload=(json.dumps({'id':'user','scopes':['read']}).encode() if req.full_url.endswith('/api/principal') else
            json.dumps({'manifest':{'revision':revision}}).encode() if req.full_url.endswith('/api/guide') else data)
   return io.BytesIO(payload)
  with tempfile.TemporaryDirectory() as t,patch.object(refresh,'build_opener',return_value=SimpleNamespace(open=response)):
   result=refresh.refresh('https://fixture.test',Path(t),'fixture')
   target=Path(result['path']);moved=target.with_name('moved');target.rename(moved);target.symlink_to(moved,target_is_directory=True)
   with self.assertRaisesRegex(ValueError,'symlink'):refresh.refresh('https://fixture.test',Path(t),'fixture')
   target.unlink();data=bundle('./entry.md')
   with self.assertRaisesRegex(ValueError,'bundle path'):refresh.refresh('https://fixture.test',Path(t),'fixture')

 def test_legacy_guide_cli_does_not_echo_secret_header_exceptions(self):
  script=Path(__file__).resolve().parents[1]/'refresh.py'
  result=subprocess.run([sys.executable,str(script),'http://127.0.0.1:9'],env={**os.environ,'LOOM_TOKEN':'fixture-secret\ninvalid-header'},capture_output=True,text=True,timeout=5)
  self.assertNotEqual(result.returncode,0);self.assertNotIn('fixture-secret',result.stdout+result.stderr)
 def test_response_envelope_json_and_sse(self):
  with tempfile.TemporaryDirectory() as t:
   path=Path(t)/'client.json';path.write_text(json.dumps({'endpoint':'http://localhost/mcp','authentication':'tailscale'}))
   client=OpsTransport(path)
   for media in ('application/json','text/event-stream'):
    for reply,valid in [({'jsonrpc':'2.0','id':1,'result':{}},True),({'jsonrpc':'2.0','id':1,'result':{'isError':True,'structuredContent':{'error':'tool_error','incident_id':'02c11225fd5740a9833b384f68aad3af'},'_meta':{'loom':{'contract_revision':'next'}}}},True),({'jsonrpc':'2.0','id':2,'result':{}},False),({'id':1,'result':{}},False),({'jsonrpc':'2.0','id':1,'result':{},'error':{}},False),([],False)]:
     raw=json.dumps(reply).encode()
     if media=='text/event-stream':raw=b'data: '+raw+b'\n\n'
     response=io.BytesIO(raw);response.status=200;response.headers=email.message.Message();response.headers['Content-Type']=media
     with self.subTest(media=media,reply=reply),patch.object(client.opener,'open',return_value=response):
      if valid:self.assertEqual(client.rpc({'jsonrpc':'2.0','id':1,'method':'tools/list'}),reply)
      else:
       with self.assertRaises(ValueError):client.rpc({'jsonrpc':'2.0','id':1,'method':'tools/list'})
 def test_nonobject_credentials_fail_cleanly(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'credential.json';p.write_text('[]');p.chmod(0o600)
   with self.assertRaisesRegex(ValueError,'Invalid credential'):read_token(p)

 def test_optional_tool_contract_and_legacy_result_refs_pass_through_unchanged(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'client.json';p.write_text(json.dumps({'endpoint':'http://localhost/mcp','authentication':'tailscale'}))
   client=OpsTransport(p)
   values=[{'name':'components','arguments':{'action':'get_tool','arguments':{'owner':'owner','id':'planner','revision':3}}},
           {'name':'components','arguments':{'action':'register_profile','arguments':{'id':'runner','profile':{'tools':{'planner':{'owner':'owner','id':'planner','revision':3}}}}}},
           {'name':'results','arguments':{'action':'historical','arguments':{'source':'catalog','kind':'model','id':'policy','revision':'original-snapshot'}}}]
   for i,value in enumerate(values):
    reply={'jsonrpc':'2.0','id':i,'result':{'content':[{'type':'text','text':json.dumps(value)}]}}
    response=io.BytesIO(json.dumps(reply).encode());response.status=200;response.headers=email.message.Message();response.headers['Content-Type']='application/json'
    message={'jsonrpc':'2.0','id':i,'method':'tools/call','params':value}
    with patch.object(client.opener,'open',return_value=response) as call:
     self.assertEqual(client.rpc(message),reply)
     self.assertEqual(json.loads(call.call_args.args[0].data),message)
