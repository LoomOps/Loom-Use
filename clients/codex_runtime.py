"""Bounded reconnection to an existing Codex app-server; never start a daemon."""
import errno, os, stat
try:
    from .websocket_unix import Connection
except ImportError:
    from websocket_unix import Connection
from pathlib import Path


class ControlPathError(ValueError):
    pass


def control_path(candidate):
    """Resolve user-owned socket links; peer credentials are checked on connect."""
    candidate=Path(candidate)
    try:
        # A foreign-owned link is not an authorized selector even if its target is ours.
        if candidate.lstat().st_uid!=os.getuid():raise ControlPathError('control_socket_owner_mismatch')
        path=candidate.resolve(strict=True)
        info=path.stat()
        if info.st_uid!=os.getuid():raise ControlPathError('control_socket_owner_mismatch')
        if not stat.S_ISSOCK(info.st_mode):raise ControlPathError('control_path_not_socket')
        return path
    except FileNotFoundError:
        raise ControlPathError('control_socket_missing') from None
    except PermissionError:
        raise ControlPathError('control_socket_permission_denied') from None
    except RuntimeError:
        raise ControlPathError('control_socket_link_loop') from None
    except OSError as error:
        if error.errno==errno.ELOOP:raise ControlPathError('control_socket_link_loop') from None
        raise


def discover_socket(explicit=None):
    if explicit is not None:return control_path(explicit)
    home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
    canonical=home/'app-server-control/app-server-control.sock'
    # Never fall through to another running server when the canonical selector is broken.
    if canonical.exists() or canonical.is_symlink():return control_path(canonical)
    candidates=set()
    for candidate in Path(f'/tmp/codex-daemon-{os.getuid()}').glob('*'):
        try:candidates.add(control_path(candidate))
        except ControlPathError:continue
    if not candidates:raise ControlPathError('control_socket_missing')
    if len(candidates)!=1:raise ControlPathError('control_socket_ambiguous')
    return candidates.pop()


FALLBACK=('Inspect the reported failure; use an available client MCP Restart tool first, '
          'then verify system.status and system.guide in the current chat. Ask the user '
          'to restart MCP only if no supported agent-accessible action is available. '
          'Do not restart the Codex daemon.')


def reconnect(name, cwd, thread_id=None, socket=None, timeout=6):
    cwd = Path(cwd)
    if not cwd.is_dir(): return {'status':'pending','reason':'project_directory_missing','cwd':str(cwd)}
    try:path=discover_socket(socket)
    except ControlPathError as error:
        return {'status':'pending','reason':str(error),'stage':'socket_discovery','next':FALLBACK,'installation':'unchanged','chat_verification':'pending'}
    except OSError:
        return {'status':'pending','reason':'control_socket_discovery_failed','stage':'socket_discovery','next':FALLBACK,'installation':'unchanged','chat_verification':'pending'}
    connection=None;stage="connect";refreshed=False
    try:
        connection=Connection(path,timeout);rpc=connection.rpc
        stage='initialize'
        rpc(1,'initialize',{'clientInfo':{'name':'loom-use','version':'1'},'capabilities':{'experimentalApi':True}})
        connection.send({'method':'initialized','params':{}})
        stage='refresh'
        rpc(2,'config/mcpServer/reload',{})
        rpc(3,'skills/list',{'cwds':[str(cwd)],'forceReload':True})
        refreshed=True
        if not thread_id:return {'status':'refreshed','reason':'refresh_requested_thread_unverified','verification':'unverified','cwd':str(cwd)}
        stage='thread_verification'
        status=rpc(4,'mcpServerStatus/list',{'threadId':thread_id,'serverName':name,'detail':'toolsAndAuthOnly'})
        server=next((x for x in status.get('data',[]) if x.get('name')==name),{})
        if server.get('runtimeStatus')!='connected':
            return {'status':'pending','reason':'thread_not_connected','stage':stage,'refresh_requested':True,'runtime_status':server.get('runtimeStatus')}
        # A cached tools/list is insufficient: call through this thread's connection.
        for id, action in [(5,'status'),(6,'guide')]:
            result=rpc(id,'mcpServer/tool/call',{'threadId':thread_id,'server':name,'tool':'system','arguments':{'action':action}})
            if result.get('isError'): raise ValueError('Thread tool call failed')
        return {'status':'verified','scope':'existing_codex_thread','tool_count':len(server.get('tools',{})),'cwd':str(cwd)}
    except (OSError,ValueError,KeyError,IndexError,UnicodeError) as error:
        reason=('control_socket_permission_denied' if isinstance(error,PermissionError) else
                'control_socket_connection_refused' if isinstance(error,ConnectionRefusedError) else
                'app_server_timeout' if isinstance(error,TimeoutError) else 'app_server_'+type(error).__name__)
        return {'status':'pending','reason':reason,'stage':stage,'refresh_requested':refreshed,'next':FALLBACK}
    finally:
        if connection:connection.close()
