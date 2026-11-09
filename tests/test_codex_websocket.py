"""Real Unix socket HTTP Upgrade/framing fixtures; no JSONL proxy stand-in."""
import base64,hashlib,json,os,socket,struct,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from clients import codex_runtime
from clients.websocket_unix import Connection,GUID,LIMIT

class Server:
 def __init__(self,path,mode='normal'):
  self.sock=socket.socket(socket.AF_UNIX);self.sock.bind(str(path));self.sock.listen(1)
  self.mode=mode;self.methods=[];self.errors=[];self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
 def run(self):
  try:
   conn,_=self.sock.accept();conn.settimeout(2)
   with conn:
    def take(n):
     data=b''
     while len(data)<n:
      b=conn.recv(n-len(data))
      if not b:raise EOFError()
      data+=b
     return data
    head=b''
    while not head.endswith(b'\r\n\r\n'):head+=take(1)
    assert head.startswith(b'GET / HTTP/1.1')
    key=next(line.split(b': ',1)[1] for line in head.split(b'\r\n') if line.startswith(b'Sec-WebSocket-Key:'))
    accept=base64.b64encode(hashlib.sha1(key+GUID.encode()).digest())
    if self.mode=='bad_upgrade':accept=b'invalid'
    conn.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n')
    if self.mode=='bad_upgrade':return
    if self.mode=='timeout':time.sleep(.2);return
    def frame(data,opcode=1,fin=True):
     data=data if isinstance(data,bytes) else json.dumps(data).encode();n=len(data)
     prefix=bytes([(128 if fin else 0)|opcode])
     prefix+=bytes([n]) if n<126 else bytes([126])+struct.pack('!H',n)
     conn.sendall(prefix+data)
    if self.mode=='oversize':conn.sendall(b'\x81\x7f'+struct.pack('!Q',LIMIT+1));return
    while True:
     first,second=take(2);assert second&128,'Client frames must be masked'
     n=second&127
     if n==126:n=struct.unpack('!H',take(2))[0]
     elif n==127:n=struct.unpack('!Q',take(8))[0]
     mask=take(4);raw=bytes(b^mask[i%4] for i,b in enumerate(take(n)))
     if first&15==10:continue
     m=json.loads(raw);self.methods.append(m['method'])
     if 'id' not in m:continue
     if m['method']=='mcpServerStatus/list':r={'data':[{'name':'loom-use','runtimeStatus':'connected','tools':{'system':{}}}]}
     elif m['method']=='mcpServer/tool/call':r={'isError':self.mode=='tool_error','content':[{'type':'text','text':'{}'}]}
     else:r={}
     response={'id':m['id'],'result':r}
     if self.mode=='fragmented':
      frame({'method':'notification','params':{}})
      raw=json.dumps(response).encode();frame(raw[:7],fin=False);frame(b'ping',9);frame(raw[7:],0)
     else:frame(response)
  except (EOFError,BrokenPipeError,ConnectionResetError):pass
  except Exception as e:self.errors.append(repr(e))
  finally:self.sock.close()
 def close(self):self.thread.join(3)

class WebSocketTests(unittest.TestCase):
 def exercise(self,mode='normal',thread='thread'):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);path=root/'control.sock';server=Server(path,mode)
   try:
    with patch.dict(os.environ,{'PATH':''}):
     result=codex_runtime.reconnect('loom-use',root,thread,socket=str(path),timeout=.1 if mode=='timeout' else 1)
   finally:server.close()
   self.assertFalse(server.errors,server.errors)
   return result,server.methods
 def test_upgrade_masking_and_actual_thread_calls(self):
  for mode in ('normal','fragmented'):
   result,methods=self.exercise(mode)
   self.assertEqual(result['status'],'verified')
   self.assertEqual(methods.count('mcpServer/tool/call'),2)
   self.assertIn('config/mcpServer/reload',methods)
 def test_timeout_bad_upgrade_oversize_and_tool_error_never_verify(self):
  for mode in ('timeout','bad_upgrade','oversize','tool_error'):
   result,_=self.exercise(mode)
   self.assertEqual(result['status'],'pending',mode)
 def test_no_thread_and_missing_socket_do_not_claim_runtime_verified(self):
  result,methods=self.exercise(thread=None)
  self.assertEqual(result['status'],'refreshed');self.assertEqual(result['reason'],'refresh_requested_thread_unverified');self.assertNotIn('mcpServer/tool/call',methods)
  with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'PATH':''}):
   result=codex_runtime.reconnect('loom-use',t,socket=t+'/absent')
   self.assertEqual(result['reason'],'control_socket_missing')
 def test_canonical_socket_is_discovered(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'app-server-control').mkdir();path=root/'app-server-control/app-server-control.sock';server=Server(path)
   try:
    with patch.dict(os.environ,{'CODEX_HOME':t}),patch.dict(os.environ,{'PATH':''}):
     self.assertEqual(codex_runtime.reconnect('loom-use',root,'thread')['status'],'verified')
   finally:server.close()
   self.assertFalse(server.errors)

 def test_canonical_symlink_and_explicit_symlink_complete_real_calls(self):
  for explicit in (False,True):
   with tempfile.TemporaryDirectory() as t:
    root=Path(t);(root/'app-server-control').mkdir();target=root/'actual.sock'
    canonical=root/'app-server-control/app-server-control.sock';canonical.symlink_to(target)
    server=Server(target)
    try:
     with patch.dict(os.environ,{'CODEX_HOME':t}),patch.dict(os.environ,{'PATH':''}):
      result=codex_runtime.reconnect('loom-use',root,'thread',socket=canonical if explicit else None)
      self.assertEqual(result['status'],'verified')
      self.assertEqual(server.methods.count('mcpServer/tool/call'),2)
    finally:server.close()
    self.assertFalse(server.errors)

 def test_invalid_selectors_report_reason_without_connecting(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'app-server-control').mkdir();path=root/'app-server-control/app-server-control.sock'
   with patch.dict(os.environ,{'CODEX_HOME':t}),patch.dict(os.environ,{'PATH':''}),patch.object(codex_runtime,'Connection') as connect:
    path.symlink_to(root/'missing')
    self.assertEqual(codex_runtime.reconnect('loom-use',root)['reason'],'control_socket_missing')
    path.unlink();path.symlink_to(path)
    self.assertEqual(codex_runtime.reconnect('loom-use',root)['reason'],'control_socket_link_loop')
    path.unlink();path.write_text('not a socket')
    self.assertEqual(codex_runtime.reconnect('loom-use',root)['reason'],'control_path_not_socket')
    connect.assert_not_called()

 def test_foreign_owner_and_ambiguous_fallback_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);target=root/'actual.sock';s=socket.socket(socket.AF_UNIX);s.bind(str(target))
   link=root/'link';link.symlink_to(target)
   try:
    with patch.object(codex_runtime.os,'getuid',return_value=os.getuid()+1):
     with self.assertRaisesRegex(codex_runtime.ControlPathError,'owner_mismatch'):codex_runtime.control_path(link)
    with patch.dict(os.environ,{'CODEX_HOME':t}),patch.object(Path,'glob',return_value=[target,link]):
     self.assertEqual(codex_runtime.discover_socket(),target)
    other=root/'other.sock';s2=socket.socket(socket.AF_UNIX);s2.bind(str(other))
    try:
     with patch.dict(os.environ,{'CODEX_HOME':t}),patch.object(Path,'glob',return_value=[target,other]):
      with self.assertRaisesRegex(codex_runtime.ControlPathError,'ambiguous'):codex_runtime.discover_socket()
    finally:s2.close()
   finally:s.close()

 def test_refused_socket_is_not_reported_as_missing_api(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);path=root/'closed.sock';s=socket.socket(socket.AF_UNIX);s.bind(str(path));s.close()
   with patch.dict(os.environ,{'PATH':''}):
    result=codex_runtime.reconnect('loom-use',root,socket=path)
   self.assertEqual(result['reason'],'control_socket_connection_refused')
   self.assertEqual(result['stage'],'connect')
