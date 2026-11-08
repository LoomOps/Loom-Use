"""Bounded reconnection to an existing Codex app-server; never start a daemon."""
import json, os, selectors, shutil, subprocess, time
from pathlib import Path


def reconnect(name, cwd, thread_id=None, socket=None, timeout=6):
    cwd = Path(cwd)
    if not cwd.is_dir(): return {'status':'pending','reason':'project_directory_missing','cwd':str(cwd)}
    binary = shutil.which('codex')
    if not binary: return {'status':'pending','reason':'codex_not_found'}
    # A control socket or application-supported API is required. Do not launch
    # a standalone app-server and mistake its catalog for the user's thread.
    if socket is None:
        candidates = list(Path(f'/tmp/codex-daemon-{os.getuid()}').glob('*'))
        candidates = [p for p in candidates if p.is_socket() and p.stat().st_uid == os.getuid()]
        if len(candidates) != 1: return {'status':'pending','reason':'app_server_control_unavailable'}
        socket = str(candidates[0])
    process = subprocess.Popen([binary,'app-server','proxy','--sock',str(socket)],cwd=cwd,
                               stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    selector=selectors.DefaultSelector(); selector.register(process.stdout,selectors.EVENT_READ)
    buffer=b''
    def rpc(id, method, params):
        nonlocal buffer
        process.stdin.write((json.dumps({'id':id,'method':method,'params':params})+'\n').encode());process.stdin.flush()
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            for key,_ in selector.select(min(.25,max(0,end-time.monotonic()))):
                chunk=os.read(key.fileobj.fileno(),65536)
                if not chunk: raise OSError('App server disconnected')
                buffer+=chunk
                if len(buffer)>4*1024*1024: raise ValueError('App server response limit')
                while b'\n' in buffer:
                    line,buffer=buffer.split(b'\n',1)
                    response=json.loads(line)
                    if response.get('id')==id:
                        if 'error' in response: raise ValueError('App server rejected request')
                        return response['result']
        raise TimeoutError()
    try:
        rpc(1,'initialize',{'clientInfo':{'name':'loom-use','version':'1'},'capabilities':{'experimentalApi':True}})
        process.stdin.write(b'{"method":"initialized","params":{}}\n');process.stdin.flush()
        rpc(2,'config/mcpServer/reload',{})
        rpc(3,'skills/list',{'cwds':[str(cwd)],'forceReload':True})
        if not thread_id: return {'status':'pending','reason':'refresh_requested_thread_unverified'}
        status=rpc(4,'mcpServerStatus/list',{'threadId':thread_id,'serverName':name,'detail':'toolsAndAuthOnly'})
        server=next((x for x in status.get('data',[]) if x.get('name')==name),{})
        if server.get('runtimeStatus')!='connected':
            return {'status':'pending','reason':'thread_not_connected','runtime_status':server.get('runtimeStatus')}
        # A cached tools/list is insufficient: call through this thread's connection.
        for id, action in [(5,'status'),(6,'guide')]:
            result=rpc(id,'mcpServer/tool/call',{'threadId':thread_id,'server':name,'tool':'system','arguments':{'action':action}})
            if result.get('isError'): raise ValueError('Thread tool call failed')
        return {'status':'verified','scope':'existing_codex_thread','tool_count':len(server.get('tools',{}))}
    except (OSError,ValueError,TimeoutError) as error:
        return {'status':'pending','reason':'app_server_'+type(error).__name__,'next':'Use Codex MCP Restart, then run doctor with the current thread ID.'}
    finally:
        selector.close();process.terminate()
        try: process.wait(3)
        except subprocess.TimeoutExpired: process.kill();process.wait()
        process.stdin.close();process.stdout.close()
