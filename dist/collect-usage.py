"""Read-only disk usage and WSL/Docker inventory snapshots. Python 3.10+."""
import argparse
import ctypes
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
import uuid


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run(args, timeout=12):
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        def decode(raw):
            return raw.decode('utf-16-le' if b'\x00' in raw[:100] else 'utf-8-sig', errors='replace').strip().lstrip('\ufeff')
        return result.returncode, decode(result.stdout), decode(result.stderr)
    except (OSError, subprocess.TimeoutExpired) as error:
        return -1, '', 'Command timed out' if isinstance(error, subprocess.TimeoutExpired) else 'Command unavailable'


def scan_tree(root, max_depth=4, seconds=45, max_nodes=4000):
    """Count readable file lengths; never follow junctions/symlinks or read contents."""
    deadline = time.monotonic() + seconds
    budget = [max_nodes]
    def visit(directory, depth):
        node = dict(name=Path(directory).name or str(directory), bytes=0, files=0, directories=0,
                    errors=0, skipped=0, partial=False, truncated=False, children=[])
        direct_bytes = direct_files = 0
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if time.monotonic() >= deadline:
                        node['partial'] = True
                        break
                    try:
                        metadata = entry.stat(follow_symlinks=False)
                        if entry.is_symlink() or (entry.is_dir(follow_symlinks=False) and getattr(metadata, 'st_file_attributes', 0) & 0x400):
                            node['skipped'] += 1
                            continue
                        if stat.S_ISDIR(metadata.st_mode):
                            child = visit(entry.path, depth + 1)
                            node['bytes'] += child['bytes']
                            node['files'] += child['files']
                            node['directories'] += child['directories'] + 1
                            node['errors'] += child['errors']
                            node['skipped'] += child['skipped']
                            node['partial'] |= child['partial']
                            if depth < max_depth and budget[0] > 0:
                                budget[0] -= 1
                                node['children'].append(child)
                            else:
                                node['truncated'] = True
                        elif stat.S_ISREG(metadata.st_mode):
                            direct_bytes += metadata.st_size
                            direct_files += 1
                    except OSError:
                        node['errors'] += 1
        except OSError:
            node['errors'] += 1
        node['bytes'] += direct_bytes
        node['files'] += direct_files
        # Group files in their directory; individual file names and contents are not collected.
        retained = sum(child['bytes'] for child in node['children'])
        if node['children'] and (node['bytes'] > retained or direct_files):
            node['children'].append(dict(name='[files / deeper folders]', bytes=node['bytes'] - retained,
                                         files=direct_files, directories=0, errors=0, skipped=0,
                                         partial=False, truncated=node['truncated'], children=[]))
        node['children'].sort(key=lambda child: child['bytes'], reverse=True)
        return node
    started = time.monotonic()
    result = visit(os.fspath(root), 0)
    result['durationSeconds'] = round(time.monotonic() - started, 2)
    return result


def windows_volumes():
    command = "$physical=@(Get-CimInstance Win32_LogicalDiskToPartition | ForEach-Object {$_.Dependent.DeviceID}); @(Get-CimInstance Win32_LogicalDisk | Where-Object DriveType -EQ 3 | ForEach-Object {[pscustomobject]@{drive=$_.DeviceID;fileSystem=$_.FileSystem;sizeBytes=$_.Size;freeBytes=$_.FreeSpace;physical=($physical -contains $_.DeviceID)}}) | ConvertTo-Json -Compress"
    code, output, _ = run(['powershell.exe', '-NoProfile', '-Command', command], 20)
    if code:
        raise RuntimeError('Cannot enumerate Windows volumes')
    values = json.loads(output)
    return values if isinstance(values, list) else [values]


def collect_storage(drives=None, seconds=45, depth=4):
    result = dict(id=uuid.uuid4().hex, capturedAt=now(), maxDepth=depth, volumes=[])
    for volume in windows_volumes():
        selected = volume['drive'].lower() in [d.rstrip('\\/').lower() for d in drives] if drives else volume['physical']
        volume['usedBytes'] = max(0, volume['sizeBytes'] - volume['freeBytes'])
        volume['tree'] = None
        volume['status'] = 'not-scanned'
        volume['note'] = 'No physical partition mapping; use --drives to include this volume'
        if selected:
            print(f"Scanning {volume['drive']} (budget {seconds}s)", flush=True)
            volume['tree'] = scan_tree(volume['drive'] + '\\', depth, seconds)
            tree = volume['tree']
            volume['status'] = 'partial' if tree['partial'] or tree['errors'] else 'complete'
            volume['note'] = 'Readable file lengths; system/protected files may be omitted'
        result['volumes'].append(volume)
    result['completedAt'] = now()
    return result


def vhd_size(filename):
    info = dict(fileName=Path(filename).name, fileBytes=None, allocatedBytes=None)
    try:
        info['fileBytes'] = os.stat(filename).st_size
        if os.name == 'nt':
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetCompressedFileSizeW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
            kernel.GetCompressedFileSizeW.restype = ctypes.c_ulong
            high = ctypes.c_ulong()
            ctypes.set_last_error(0)
            low = kernel.GetCompressedFileSizeW(str(filename), ctypes.byref(high))
            if low != 0xFFFFFFFF or ctypes.get_last_error() == 0:
                info['allocatedBytes'] = (high.value << 32) | low
    except OSError:
        pass
    return info


def collect_wsl():
    result = dict(available=bool(shutil.which('wsl.exe')), status='unavailable', distributions=[])
    if not result['available']:
        return result
    code, verbose, _ = run(['wsl.exe', '--list', '--verbose'])
    _, running, _ = run(['wsl.exe', '--list', '--running', '--quiet'])
    if code:
        return result
    running_names = set(running.splitlines())
    result['status'] = 'available'
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Lxss') as key:
            for index in range(winreg.QueryInfoKey(key)[0]):
                with winreg.OpenKey(key, winreg.EnumKey(key, index)) as distro:
                    def read(name, fallback=''):
                        try:
                            return winreg.QueryValueEx(distro, name)[0]
                        except OSError:
                            return fallback
                    name = read('DistributionName')
                    base = Path(read('BasePath'))
                    disks = [vhd_size(file) for file in base.glob('*.vhdx')]
                    item = dict(name=name, version=read('Version', 2), state='running' if name in running_names else 'stopped', disks=disks, filesystem=None, osName=name, osSource='registered-name')
                    if item['state'] == 'running':
                        os_code, release, _ = run(['wsl.exe', '--distribution', name, '--exec', 'cat', '/etc/os-release'])
                        if not os_code:
                            fields = dict(line.split('=', 1) for line in release.splitlines() if '=' in line)
                            item['osName'] = fields.get('PRETTY_NAME', name).strip('"')
                            item['osSource'] = 'os-release'
                        exit_code, output, _ = run(['wsl.exe', '--distribution', name, '--exec', 'df', '-B1', '-P', '/'])
                        if not exit_code:
                            fields = output.splitlines()[-1].split()
                            if len(fields) >= 6 and fields[1].isdigit():
                                item['filesystem'] = dict(sizeBytes=int(fields[1]), usedBytes=int(fields[2]), freeBytes=int(fields[3]))
                    result['distributions'].append(item)
    except OSError:
        result['status'] = 'unavailable'
    return result


def docker_rows(args):
    code, output, _ = run(['docker', *args, '--format', '{{json .}}'], 20)
    if code:
        return None
    try:
        return [json.loads(line) for line in output.splitlines() if line.strip()]
    except ValueError:
        return None


def collect_docker():
    result = dict(available=bool(shutil.which('docker')), status='unavailable', summary=[], containers=[], images=[], volumes=[], disks=[], warnings=[], operatingSystem='', osType='', architecture='', kernelVersion='', serverVersion='')
    # Docker Desktop's disk may exist even when its engine is stopped.
    local = os.environ.get('LOCALAPPDATA')
    if local:
        root = Path(local) / 'Docker' / 'wsl'
        if root.exists():
            result['disks'] = [vhd_size(file) for file in root.glob('**/*.vhdx')]
    if not result['available']:
        return result
    context_code, context_name, _ = run(['docker', 'context', 'show'])
    result['context'] = context_name if not context_code else ''
    # Only inventory a local daemon. Never send commands to a remote Docker context.
    endpoint = os.environ.get('DOCKER_HOST', '')
    code, context_json, _ = run(['docker', 'context', 'inspect'])
    if not code:
        try:
            endpoint = endpoint or json.loads(context_json)[0]['Endpoints']['docker']['Host']
        except (ValueError, KeyError, IndexError):
            pass
    if not endpoint or not endpoint.startswith(('npipe://', 'unix://')):
        result['status'] = 'remote-context'
        return result
    summary = docker_rows(['system', 'df'])
    if summary is None:
        result['status'] = 'engine-unavailable'
        return result
    result['status'] = 'available'
    code, info, _ = run(['docker','info','--format','{"operatingSystem":{{json .OperatingSystem}},"osType":{{json .OSType}},"architecture":{{json .Architecture}},"kernelVersion":{{json .KernelVersion}},"serverVersion":{{json .ServerVersion}}}'])
    if not code:
        try:
            result.update(json.loads(info))
        except ValueError:
            result['warnings'].append('Unable to read engine OS')
    result['summary'] = [dict(type=row.get('Type',''), totalCount=str(row.get('TotalCount','')), active=str(row.get('Active','')), size=row.get('Size',''), reclaimable=row.get('Reclaimable','')) for row in summary]
    queries = [
        ('containers', ['ps','--all','--size'], {'name':'Names','image':'Image','state':'State','status':'Status','size':'Size'}),
        ('images', ['image','ls'], {'repository':'Repository','tag':'Tag','id':'ID','size':'Size','created':'CreatedSince'}),
        ('volumes', ['volume','ls'], {'name':'Name','driver':'Driver','scope':'Scope'}),
    ]
    for key, args, mapping in queries:
        rows = docker_rows(args)
        if rows is None:
            result['warnings'].append(f'Unable to read {key}')
        else:
            result[key] = [{dest:str(row.get(source,'')) for dest,source in mapping.items()} for row in rows]
    ids = list(dict.fromkeys(image['id'] for image in result['images'] if image['id']))
    platforms = {}
    for index in range(0, len(ids), 50):
        code, output, _ = run(['docker','image','inspect','--format','{"id":{{json .Id}},"os":{{json .Os}},"architecture":{{json .Architecture}},"sizeBytes":{{json .Size}}}',*ids[index:index+50]], 25)
        if not code:
            for line in output.splitlines():
                try:
                    details=json.loads(line)
                    platforms[details['id'].removeprefix('sha256:')[:12]]=details
                except (ValueError, KeyError):
                    pass
    for image in result['images']:
        platform=platforms.get(image['id'].removeprefix('sha256:')[:12],{})
        image.update(os=platform.get('os',''),architecture=platform.get('architecture',''),sizeBytes=platform.get('sizeBytes'))
    return result


def collect_environments():
    return dict(id=uuid.uuid4().hex, capturedAt=now(), wsl=collect_wsl(), docker=collect_docker(), completedAt=now())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--computer', required=True, help='Existing PC specification JSON to update')
    parser.add_argument('--kind', choices=['storage','environments','all'], default='all')
    parser.add_argument('--drives', nargs='+', help='Volumes to scan; default: physically mapped local volumes')
    parser.add_argument('--seconds-per-volume', type=float, default=45)
    parser.add_argument('--depth', type=int, default=4)
    parser.add_argument('--output', help='Default: update --computer atomically')
    args = parser.parse_args()
    if not 0 < args.seconds_per_volume <= 3600 or not 1 <= args.depth <= 8:
        parser.error('seconds-per-volume must be 0..3600 and depth must be 1..8')
    filename = Path(args.computer)
    pc = json.loads(filename.read_text(encoding='utf-8-sig'))
    if pc.get('schemaVersion') != 1 or not isinstance(pc.get('hardware'),dict):
        parser.error('Please provide an existing PC specification JSON')
    if args.kind in ('environments','all'):
        snapshot = collect_environments()
        pc['subsystems'] = snapshot
        pc.pop('environmentSnapshots', None)
        print(f"WSL: {len(snapshot['wsl']['distributions'])} distributions; Docker: {snapshot['docker']['status']}", flush=True)
    if args.kind in ('storage','all'):
        pc['storageSnapshots'] = (pc.get('storageSnapshots', []) + [collect_storage(args.drives,args.seconds_per_volume,args.depth)])[-20:]
    output = Path(args.output) if args.output else filename
    temporary = output.with_name(output.name + '.tmp')
    temporary.write_text(json.dumps(pc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, output)
    print(f'Saved snapshot: {output}', flush=True)


if __name__ == '__main__':
    main()
