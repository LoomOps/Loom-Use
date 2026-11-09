"""Bounded reconnection to an existing Codex app-server; never start a daemon."""
import os, shutil
try:
    from .websocket_unix import Connection
except ImportError:
    from websocket_unix import Connection
from pathlib import Path


def reconnect(name, cwd, thread_id=None, socket=None, timeout=6):
    cwd = Path(cwd)
    if not cwd.is_dir(): return {'status':'pending','reason':'project_directory_missing','cwd':str(cwd)}
    binary = shutil.which('codex')
    if not binary: return {'status':'pending','reason':'codex_not_found'}
    # Use the running server only. Prefer its canonical user-owned control path.
    if socket is None:
        home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
        canonical=home/'app-server-control/app-server-control.sock'
        candidates=[canonical] if canonical.is_socket() else list(Path(f'/tmp/codex-daemon-{os.getuid()}').glob('*'))
        candidates=[p for p in candidates if p.is_socket() and not p.is_symlink() and p.stat().st_uid==os.getuid()]
        if len(candidates)!=1:return {'status':'pending','reason':'app_server_control_unavailable'}
        socket=str(candidates[0])
    path=Path(socket)
    if not path.is_socket() or path.is_symlink() or path.stat().st_uid!=os.getuid():
        return {'status':'pending','reason':'app_server_control_unavailable'}
    connection=None
    try:
        connection=Connection(path,timeout);rpc=connection.rpc
        rpc(1,'initialize',{'clientInfo':{'name':'loom-use','version':'1'},'capabilities':{'experimentalApi':True}})
        connection.send({'method':'initialized','params':{}})
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
    except (OSError,ValueError,KeyError,IndexError,UnicodeError) as error:
        return {'status':'pending','reason':'app_server_'+type(error).__name__,'next':'Use Codex MCP Restart, then run doctor with the current thread ID.'}
    finally:
        if connection:connection.close()
