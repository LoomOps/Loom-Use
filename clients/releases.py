"""Pinned, checksum-verified client packages; no execution during download."""
import hashlib, io, json, re, shutil, stat, tempfile, zipfile
from pathlib import Path
from urllib.request import urlopen

REPOSITORY = 'LoomOps/Loom-Use'
LIMIT = 8 * 1024 * 1024


def validate(lock):
    version = lock.get('version', '')
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[a-z]+\.\d+)?', version):
        raise ValueError('Invalid Loom Use release version')
    expected = f'https://github.com/{REPOSITORY}/releases/download/v{version}/loom-use-{version}.zip'
    if lock.get('url') != expected or not re.fullmatch('[a-f0-9]{64}', lock.get('sha256', '')):
        raise ValueError('Untrusted Loom Use release descriptor')
    return lock


def install(lock, parent):
    validate(lock)
    parent = Path(parent); parent.mkdir(parents=True, exist_ok=True)
    target = parent / lock['version']
    if target.is_symlink(): raise ValueError('Release target must not be a symlink')
    if target.exists():
        verify(target, lock)
        return target
    with urlopen(lock['url'], timeout=30) as response:
        data = response.read(LIMIT + 1)
    return unpack(data, lock, parent)


def unpack(data, lock, parent):
    validate(lock)
    if len(data) > LIMIT or hashlib.sha256(data).hexdigest() != lock['sha256']:
        raise ValueError('Client package checksum mismatch')
    parent = Path(parent); parent.mkdir(parents=True, exist_ok=True)
    target = parent / lock['version']
    if target.exists() or target.is_symlink():
        verify(target, lock); return target
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist(); names = [e.filename for e in entries]
        if len(set(names)) != len(names) or sum(e.file_size for e in entries) > LIMIT:
            raise ValueError('Invalid client package size or duplicate members')
        for e in entries:
            p = Path(e.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in e.filename or e.is_dir() or stat.S_ISLNK(e.external_attr >> 16) or e.filename == '.verified.json':
                raise ValueError('Unsafe client package member')
        if archive.read('VERSION').decode().strip() != lock['version']:
            raise ValueError('Client package version mismatch')
        for name in ('INSTALL.md', 'loom_use.py', 'skills/loom-use/SKILL.md', 'clients/headers.py'):
            if name not in names: raise ValueError('Incomplete client package')
        with tempfile.TemporaryDirectory(dir=parent, prefix='.download-') as temp:
            stage = Path(temp)/'release'; stage.mkdir()
            hashes = {}
            for e in entries:
                content = archive.read(e.filename); p = stage/e.filename
                p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(content); p.chmod(0o600)
                hashes[e.filename] = hashlib.sha256(content).hexdigest()
            (stage/'.verified.json').write_text(json.dumps({'lock':lock, 'files':hashes}))
            stage.rename(target)
    return target


def verify(target, lock):
    if target.is_symlink(): raise ValueError('Release target must not be a symlink')
    receipt = json.loads((target/'.verified.json').read_text())
    if receipt['lock'] != lock: raise ValueError('Existing release differs; retained')
    for name, digest in receipt['files'].items():
        p = target/name
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            raise ValueError('Installed client changed; retained without overwrite')
    return target
