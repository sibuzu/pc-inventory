"""Read-only Linux inventory; compatible with Python 3.4 and Docker 1.13+."""
from __future__ import print_function
import argparse
import datetime
import http.client
import json
import os
import platform
import re
import shlex
import socket
import stat
import subprocess
import sys
import time
import uuid
AI_PROBE_SOURCE = None


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path):
    try:
        with open(path, 'r') as handle:
            return handle.read().strip()
    except (OSError, IOError):
        return ''


def command(args, timeout=20):
    try:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return ''
        return stdout.decode('utf-8', errors='replace').strip() if process.returncode == 0 else ''
    except OSError:
        return ''


def size(value):
    if value is None:
        return ''
    units=['B','KB','MB','GB','TB']
    value=float(value)
    index=0
    while value>=1024 and index<len(units)-1:
        value/=1024
        index+=1
    return '{0:.2f} {1}'.format(value,units[index])


def memory_modules():
    output=command(['sudo','-n','dmidecode','-t','17'],timeout=10)
    modules=[]
    for block in re.split(r'\nHandle\s+0x',output):
        if '\nMemory Device\n' not in block:continue
        fields=dict((key.strip(),value.strip()) for key,value in (line.split(':',1) for line in block.splitlines() if ':' in line))
        match=re.match(r'(\d+)\s+(MB|GB|KB)',fields.get('Size',''))
        if not match:continue
        capacity=int(match.group(1))*{'GB':1,'MB':1.0/1024,'KB':1.0/1024**2}[match.group(2)]
        speed=re.search(r'\d+',fields.get('Speed',''))
        configured=re.search(r'\d+',fields.get('Configured Clock Speed',fields.get('Configured Memory Speed','')))
        modules.append(dict(capacityGB=capacity,speedMHz=int(speed.group()) if speed else None,configuredMHz=int(configured.group()) if configured else None,
                            manufacturer=fields.get('Manufacturer',''),partNumber=fields.get('Part Number',''),slot=fields.get('Locator','')))
    return modules


def scan_tree(root, seconds, skip_mounts, max_depth=4):
    deadline = time.monotonic() + seconds
    remaining = [2200]
    def visit(path, depth):
        result = dict(name=os.path.basename(path.rstrip('/')) or '/', bytes=0, files=0, directories=0,
                      errors=0, skipped=0, partial=False, truncated=False, children=[])
        direct_files = 0
        try:
            # os.scandir is unavailable on Python 3.4.
            for name in sorted(os.listdir(path)):
                if time.monotonic() >= deadline:
                    result['partial'] = True
                    break
                filename = os.path.join(path, name)
                try:
                    info = os.lstat(filename)
                    if stat.S_ISLNK(info.st_mode) or filename in skip_mounts:
                        result['skipped'] += 1
                        continue
                    if stat.S_ISDIR(info.st_mode):
                        child = visit(filename, depth + 1)
                        for key in ('bytes', 'files', 'errors', 'skipped'):
                            result[key] += child[key]
                        result['directories'] += child['directories'] + 1
                        result['partial'] |= child['partial']
                        if depth < max_depth and remaining[0] > 0:
                            remaining[0] -= 1
                            result['children'].append(child)
                        else:
                            result['truncated'] = True
                    elif stat.S_ISREG(info.st_mode):
                        result['bytes'] += info.st_size
                        result['files'] += 1
                        direct_files += 1
                except OSError:
                    result['errors'] += 1
        except OSError:
            result['errors'] += 1
        retained = sum(child['bytes'] for child in result['children'])
        if result['children'] and (result['bytes'] > retained or direct_files):
            result['children'].append(dict(name='[files / deeper folders]', bytes=result['bytes'] - retained,
                                          files=direct_files, directories=0, errors=0, skipped=0,
                                          partial=False, truncated=result['truncated'], children=[]))
        result['children'].sort(key=lambda item: item['bytes'], reverse=True)
        return result
    return visit(root, 0)


def docker_inventory():
    result = dict(available=bool(command(['docker', '--version'])), status='unavailable', context='local Unix socket',
                  operatingSystem='', osType='', architecture='', kernelVersion='', serverVersion='',
                  summary=[], containers=[], images=[], volumes=[], disks=[], warnings=[])
    if not result['available']:
        return result
    docker_host = os.environ.get('DOCKER_HOST', '')
    if docker_host and not docker_host.startswith('unix://'):
        result['status'] = 'remote-context'
        return result
    socket_path = docker_host[7:] if docker_host else '/var/run/docker.sock'
    def api(path, timeout=25):
        connection = http.client.HTTPConnection('localhost', timeout=timeout)
        try:
            connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            connection.sock.settimeout(timeout)
            connection.sock.connect(socket_path)
            connection.request('GET', path)
            response = connection.getresponse()
            return json.loads(response.read().decode('utf-8')) if response.status == 200 else None
        except (OSError, ValueError, http.client.HTTPException):
            return None
        finally:
            connection.close()
    info = api('/info')
    if not info:
        result['status'] = 'engine-unavailable'
        return result
    result['status'] = 'available'
    for destination, source in [('operatingSystem','OperatingSystem'), ('osType','OSType'), ('architecture','Architecture'),
                                ('kernelVersion','KernelVersion'), ('serverVersion','ServerVersion')]:
        result[destination] = info.get(source, '')
    print('Reading Docker images, containers and disk usage...', file=sys.stderr, flush=True)
    usage = api('/system/df', timeout=45)
    images = (usage.get('Images') if usage else None) or api('/images/json') or []
    containers = api('/containers/json?all=1&size=1') or []
    volumes = (usage.get('Volumes') if usage else None)
    if volumes is None:
        volumes = (api('/volumes') or {}).get('Volumes') or []
    deadline = time.monotonic() + 60
    platform_missing = 0
    for image in images:
        detail = api('/images/' + image['Id'] + '/json', timeout=4) if time.monotonic() < deadline else None
        if not detail:
            platform_missing += 1
        tags = image.get('RepoTags') or ['<none>:<none>']
        for tag in tags:
            repository, _, tagname = tag.rpartition(':')
            result['images'].append(dict(repository=repository or tag, tag=tagname or '<none>',
                id=image['Id'].replace('sha256:', '')[:12], size=size(image.get('Size')), sizeBytes=image.get('Size'),
                os=(detail or {}).get('Os', ''), architecture=(detail or {}).get('Architecture', ''), created=''))
    if platform_missing:
        result['warnings'].append('Image platform metadata unavailable for {0} images'.format(platform_missing))
    for container in containers:
        result['containers'].append(dict(name=', '.join(name.lstrip('/') for name in container.get('Names', [])),
            image=container.get('Image', ''), state=container.get('State', ''), status=container.get('Status', ''),
            size='{0} (virtual {1})'.format(size(container.get('SizeRw')), size(container.get('SizeRootFs')))))
    for volume in volumes:
        data = volume.get('UsageData') or {}
        result['volumes'].append(dict(name=volume.get('Name', ''), driver=volume.get('Driver', ''), scope=volume.get('Scope','local'),
            sizeBytes=data.get('Size') if data.get('Size', -1) >= 0 else None,
            refCount=data.get('RefCount') if data.get('RefCount', -1) >= 0 else None))
    result['summary'] = [
        dict(type='Images', totalCount=str(len(images)), active=str(sum(1 for image in images if image.get('Containers', 0) > 0)),
             size=size(usage.get('LayersSize')) if usage else '', reclaimable=''),
        dict(type='Containers', totalCount=str(len(containers)), active=str(sum(1 for c in containers if c.get('State') == 'running')),
             size=size(sum(c.get('SizeRw', 0) or 0 for c in containers)), reclaimable=''),
        dict(type='Local Volumes', totalCount=str(len(volumes)), active=str(sum(1 for v in volumes if (v.get('UsageData') or {}).get('RefCount', 0) > 0)),
             size=size(sum(v['sizeBytes'] for v in result['volumes'] if v['sizeBytes'] is not None)), reclaimable='')]
    result['warnings'].append('Docker usage is read-only. Reclaimable space and build cache are not supplied by this collector; shared image layers are not summed.')
    if not usage:
        result['warnings'].append('Engine disk-usage API was unavailable; shared image total and per-volume usage are unknown.')
    return result


def inventory(name, storage_seconds):
    captured = now()
    release = dict(line.split('=', 1) for line in read('/etc/os-release').splitlines() if '=' in line)
    release = dict((key, value.strip('"')) for key, value in release.items())
    entries = []
    for block in read('/proc/cpuinfo').split('\n\n'):
        entry = dict((k.strip(), v.strip()) for k, v in (line.split(':', 1) for line in block.splitlines() if ':' in line))
        if entry:
            entries.append(entry)
    sockets = sorted(set(e.get('physical id', '0') for e in entries))
    cpus = []
    for socket_id in sockets:
        processors = [e for e in entries if e.get('physical id','0') == socket_id]
        cores = len(set(e.get('core id', e.get('processor','0')) for e in processors))
        maximum = read('/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq')
        cpus.append(dict(name=processors[0].get('model name','Unknown'), cores=cores, threads=len(processors),
                         maxClockMHz=int(maximum)//1000 if maximum.isdigit() else None))
    mem = re.search(r'^MemTotal:\s+(\d+)', read('/proc/meminfo'), re.M)
    memory_gb = round(int(mem.group(1)) / 1024.0 ** 2, 2) if mem else None
    modules=memory_modules()
    if modules:memory_gb=sum(item['capacityGB'] for item in modules)
    dmi = lambda filename: read('/sys/class/dmi/id/' + filename)
    disks = []
    for line in command(['lsblk','-b','-P','-o','NAME,TYPE,SIZE,MODEL']).splitlines():
        values = dict(part.split('=',1) for part in shlex.split(line) if '=' in part)
        if values.get('TYPE') != 'disk':
            continue
        dev = values['NAME']
        disks.append(dict(name=values.get('MODEL') or read('/sys/block/'+dev+'/device/model') or 'Disk '+dev,
                          sizeGB=round(int(values['SIZE'])/1024.0**3, 1), interface='NVMe' if dev.startswith('nvme') else 'block', mediaType='SSD' if read('/sys/block/'+dev+'/queue/rotational')=='0' else 'HDD'))
    gpu = []
    for line in command(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader,nounits']).splitlines():
        parts = [part.strip() for part in line.split(',')]
        if len(parts) == 3:
            try:
                gpu.append(dict(name=parts[0], vramMB=float(parts[1]), driver=parts[2], virtual=False))
            except ValueError:
                pass
    volumes = []
    for line in command(['df','-PT','-B1']).splitlines()[1:]:
        parts = line.split(None, 6)
        if len(parts) != 7 or not parts[0].startswith('/dev/'):
            continue
        volumes.append(dict(drive=parts[6], fileSystem=parts[1], sizeBytes=int(parts[2]), usedBytes=int(parts[3]), freeBytes=int(parts[4]), physical=True, tree=None, status='not-scanned'))
    network = []
    for interface in os.listdir('/sys/class/net'):
        if interface == 'lo':
            continue
        speed = read('/sys/class/net/'+interface+'/speed')
        network.append(dict(name=interface, connected=read('/sys/class/net/'+interface+'/operstate')=='up', speedMbps=int(speed) if speed.isdigit() else None))
    software = []
    for line in command(['dpkg-query','-W','-f=${Package}\t${Version}\t${Maintainer}\t${Status}\n']).splitlines():
        parts=line.split('\t')
        if len(parts)==4 and parts[3]=='install ok installed':
            software.append(dict(name=parts[0], version=parts[1], publisher=parts[2]))
    tools=[]
    for tool,args in [('Python',['python3','--version']),('Git',['git','--version']),('Node.js',['node','--version']),('Docker',['docker','--version']),('CUDA compiler',['nvcc','--version'])]:
        version=command(args,timeout=5)
        if version:
            tools.append(dict(name=tool, version=version.replace('\n',' ')))
    docker=docker_inventory()
    ai=None
    if AI_PROBE_SOURCE:
        print('Inspecting CUDA/PyTorch environments...',file=sys.stderr,flush=True)
        namespace={'__name__':'pc_atlas_ai'}
        exec(compile(AI_PROBE_SOURCE,'ai-probe.py','exec'),namespace)
        ai=namespace['collect_ai']()
    subsystems=dict(id=uuid.uuid4().hex,capturedAt=now(),completedAt=now(),wsl=dict(available=False,status='not-applicable',distributions=[]),docker=docker)
    mounts=set()
    for line in read('/proc/self/mountinfo').splitlines():
        fields=line.split()
        if len(fields)>4 and fields[4]!='/':
            mounts.add(fields[4].replace('\\040',' '))
    snapshot=dict(id=uuid.uuid4().hex,capturedAt=now(),maxDepth=4,volumes=volumes)
    for volume in volumes:
        print('Scanning {0}, budget {1}s...'.format(volume['drive'],storage_seconds),file=sys.stderr,flush=True)
        tree=scan_tree(volume['drive'],storage_seconds,mounts-set([volume['drive']]))
        volume['tree']=tree
        volume['status']='partial' if tree['partial'] or tree['errors'] else 'complete'
    snapshot['completedAt']=now()
    return dict(schemaVersion=1,id=name,name=name,status='collected',collectedAt=captured,
        source='Linux /proc /sys / dpkg / Docker API (SSH)',
        hardware=dict(manufacturer=dmi('sys_vendor'),model=dmi('product_name'),cpu=cpus,memoryGB=memory_gb,memorySource='dmi' if modules else 'os-visible',memory=modules,gpu=gpu,
            motherboard=[dict(manufacturer=dmi('board_vendor'),product=dmi('board_name'),version=dmi('board_version'))],
            bios=dict(manufacturer=dmi('bios_vendor'),version=dmi('bios_version')),disks=disks,
            volumes=[dict(drive=v['drive'],fileSystem=v['fileSystem'],sizeGB=round(v['sizeBytes']/1024.0**3,1),freeGB=round(v['freeBytes']/1024.0**3,1)) for v in volumes],network=network),
        os=dict(name=release.get('PRETTY_NAME','Linux'),version=release.get('VERSION_ID',''),build=platform.release(),architecture=platform.machine()),
        software=sorted(software,key=lambda item:item['name']),tools=tools,storageSnapshots=[snapshot],subsystems=subsystems,ai=ai,
        warnings=[] if modules else ['Memory is OS-visible MemTotal; physical DIMM details require DMI access.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name',required=True)
    parser.add_argument('--storage-seconds',type=float,default=45)
    args=parser.parse_args()
    if not re.match(r'^[a-zA-Z0-9_-]{1,48}$',args.name) or not 0<args.storage_seconds<=600:
        parser.error('Invalid name or scan budget')
    print(json.dumps(inventory(args.name,args.storage_seconds),ensure_ascii=True))
