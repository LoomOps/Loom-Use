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
    with patch.object(codex_runtime.shutil,'which',return_value='/fixture/codex'):
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
  self.assertEqual(result['reason'],'refresh_requested_thread_unverified');self.assertNotIn('mcpServer/tool/call',methods)
  with tempfile.TemporaryDirectory() as t,patch.object(codex_runtime.shutil,'which',return_value='/fixture/codex'):
   result=codex_runtime.reconnect('loom-use',t,socket=t+'/absent')
   self.assertEqual(result['reason'],'app_server_control_unavailable')
 def test_canonical_socket_is_discovered(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'app-server-control').mkdir();path=root/'app-server-control/app-server-control.sock';server=Server(path)
   try:
    with patch.dict(os.environ,{'CODEX_HOME':t}),patch.object(codex_runtime.shutil,'which',return_value='/fixture/codex'):
     self.assertEqual(codex_runtime.reconnect('loom-use',root,'thread')['status'],'verified')
   finally:server.close()
   self.assertFalse(server.errors)
