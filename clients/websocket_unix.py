"""Minimal bounded RFC6455 client for the local Codex control socket."""
import base64, hashlib, json, os, socket, struct, time

LIMIT=4*1024*1024
GUID='258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

class Connection:
    def __init__(self,path,timeout=6):
        self.timeout=timeout;self.buffer=b'';self.socket=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        try:
            self.socket.settimeout(timeout);self.socket.connect(str(path))
            if hasattr(socket,'SO_PEERCRED'):
                _,uid,_=struct.unpack('3i',self.socket.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                if uid!=os.getuid():raise ValueError('Control socket belongs to another user')
            key=base64.b64encode(os.urandom(16)).decode()
            self.socket.sendall(('GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: '+key+'\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
            deadline=time.monotonic()+timeout
            while b'\r\n\r\n' not in self.buffer:
                self.receive(deadline)
                if len(self.buffer)>65536:raise ValueError('Upgrade response limit')
            head,self.buffer=self.buffer.split(b'\r\n\r\n',1)
            lines=head.decode('ascii').split('\r\n');headers={}
            for line in lines[1:]:
                name,value=line.split(':',1);headers[name.lower()]=value.strip()
            accept=base64.b64encode(hashlib.sha1((key+GUID).encode()).digest()).decode()
            if (lines[0].split()[1]!='101' or headers.get('sec-websocket-accept')!=accept
                or headers.get('upgrade','').lower()!='websocket'
                or 'upgrade' not in [v.strip() for v in headers.get('connection','').lower().split(',')]):
                raise ValueError('Invalid WebSocket upgrade')
        except BaseException:self.close();raise

    def close(self):self.socket.close()

    def receive(self,deadline):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError()
        self.socket.settimeout(remaining)
        chunk=self.socket.recv(65536)
        if not chunk:raise OSError('Control socket disconnected')
        self.buffer+=chunk

    def take(self,n,deadline):
        while len(self.buffer)<n:self.receive(deadline)
        data,self.buffer=self.buffer[:n],self.buffer[n:];return data

    def send_frame(self,opcode,data):
        size=len(data)
        if size>LIMIT:raise ValueError('Request limit')
        prefix=bytes([0x80|opcode])
        if size<126:prefix+=bytes([0x80|size])
        elif size<65536:prefix+=bytes([0x80|126])+struct.pack('!H',size)
        else:prefix+=bytes([0x80|127])+struct.pack('!Q',size)
        mask=os.urandom(4)
        self.socket.settimeout(self.timeout)
        self.socket.sendall(prefix+mask+bytes(b^mask[i%4] for i,b in enumerate(data)))

    def send(self,value):self.send_frame(1,json.dumps(value).encode())

    def read(self,deadline):
        parts=bytearray();fragmented=False
        while True:
            first,second=self.take(2,deadline);opcode=first&15;final=bool(first&128);size=second&127
            if first&112 or second&128:raise ValueError('Unsupported server frame')
            if size==126:size=struct.unpack('!H',self.take(2,deadline))[0]
            elif size==127:size=struct.unpack('!Q',self.take(8,deadline))[0]
            if size>LIMIT or len(parts)+size>LIMIT:raise ValueError('Response limit')
            if opcode>=8 and (not final or size>125):raise ValueError('Invalid control frame')
            data=self.take(size,deadline)
            if opcode==8:raise OSError('Control socket closed')
            if opcode==9:self.send_frame(10,data);continue
            if opcode==10:continue
            if opcode not in (0,1) or (opcode==0)!=fragmented:raise ValueError('Invalid text continuation')
            parts.extend(data)
            if final:return json.loads(parts.decode('utf-8'))
            fragmented=True

    def rpc(self,identity,method,params):
        self.send({'id':identity,'method':method,'params':params})
        deadline=time.monotonic()+self.timeout
        while True:
            response=self.read(deadline)
            if not isinstance(response,dict):raise ValueError('Invalid RPC response')
            if response.get('id')==identity:
                if 'error' in response:raise ValueError('App server rejected request')
                return response['result']
