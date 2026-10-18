"""Read-only QNAP inventory, compatible with the built-in Python 2.7."""
from __future__ import print_function
import argparse
import glob
import json
import os
import platform
import re
import shlex
import stat
import subprocess
import sys
import time
import uuid
try:
    import ConfigParser as configparser
except ImportError:
    import configparser


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())


def read(path):
    try:
        with open(path,'rb') as handle:return handle.read().decode('utf-8','replace').strip()
    except (OSError,IOError):return ''


def command(args,timeout=15):
    try:
        process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        started=time.time()
        while process.poll() is None:
            if time.time()-started>timeout:
                process.kill();process.communicate();return ''
            time.sleep(.02)
        output,_=process.communicate()
        return output.decode('utf-8','replace').strip() if process.returncode==0 else ''
    except OSError:return ''


def cfg(key):
    return command(['/sbin/getcfg','System',key,'-f','/etc/config/uLinux.conf'])


def dmi_fields(kind):
    output=command(['/sbin/dmidecode','-t',str(kind)])
    return dict((key.strip(),value.strip()) for key,value in (line.split(':',1) for line in output.splitlines() if ':' in line))


def modules():
    output=command(['/sbin/dmidecode','-t','17'])
    result=[]
    for block in re.split(r'\nHandle\s+0x',output):
        if '\nMemory Device\n' not in block:continue
        fields=dict((key.strip(),value.strip()) for key,value in (line.split(':',1) for line in block.splitlines() if ':' in line))
        capacity=re.match(r'(\d+)\s+(MB|GB)',fields.get('Size',''))
        if not capacity:continue
        speed=re.search(r'\d+',fields.get('Speed',''))
        configured=re.search(r'\d+',fields.get('Configured Clock Speed',''))
        result.append(dict(capacityGB=int(capacity.group(1))*(1 if capacity.group(2)=='GB' else 1./1024),
            speedMHz=int(speed.group()) if speed else None,configuredMHz=int(configured.group()) if configured else None,speedUnit='MT/s' if 'MT/s' in fields.get('Speed','') else 'MHz',
            manufacturer=fields.get('Manufacturer',''),partNumber=fields.get('Part Number',''),slot=fields.get('Locator','')))
    return result


def scan(root,seconds,mounts):
    # QNAP SSH can run Python 2 with an ASCII filesystem encoding. Keep native
    # paths as bytes and decode only names saved to JSON.
    if not isinstance(root,bytes):root=root.encode('utf-8')
    mounts=set(path if isinstance(path,bytes) else path.encode('utf-8') for path in mounts)
    deadline=time.time()+seconds
    remaining=[2200]
    def visit(path,depth):
        display=os.path.basename(path.rstrip(b'/')) or b'/'
        if isinstance(display,bytes):display=display.decode('utf-8','replace')
        result=dict(name=display,bytes=0,files=0,directories=0,errors=0,skipped=0,partial=False,truncated=False,children=[])
        direct=0
        try:
            for name in sorted(os.listdir(path)):
                if time.time()>=deadline:
                    result['partial']=True;break
                filename=os.path.join(path,name)
                try:
                    info=os.lstat(filename)
                    if stat.S_ISLNK(info.st_mode) or filename in mounts or name in (b'.snapshot',b'.snapshots',b'@Recently-Snapshot'):
                        result['skipped']+=1;continue
                    if stat.S_ISDIR(info.st_mode):
                        child=visit(filename,depth+1)
                        for key in ('bytes','files','errors','skipped'):result[key]+=child[key]
                        result['directories']+=child['directories']+1
                        result['partial']|=child['partial']
                        if depth<4 and remaining[0]>0:
                            result['children'].append(child);remaining[0]-=1
                        else:result['truncated']=True
                    elif stat.S_ISREG(info.st_mode):
                        result['bytes']+=info.st_size;result['files']+=1;direct+=1
                except OSError:result['errors']+=1
        except OSError:result['errors']+=1
        retained=sum(child['bytes'] for child in result['children'])
        if result['children'] and (result['bytes']>retained or direct):
            result['children'].append(dict(name='[files / deeper folders]',bytes=result['bytes']-retained,files=direct,directories=0,errors=0,skipped=0,partial=False,truncated=result['truncated'],children=[]))
        result['children'].sort(key=lambda child:child['bytes'],reverse=True)
        return result
    return visit(root,0)


def inventory(name,seconds):
    captured=now()
    model=command(['/sbin/getsysinfo','model']) or cfg('Model')
    version=cfg('Version');build=cfg('Build Number')
    cpuinfo=read('/proc/cpuinfo')
    processors=[]
    for block in cpuinfo.split('\n\n'):
        fields=dict((k.strip(),v.strip()) for k,v in (line.split(':',1) for line in block.splitlines() if ':' in line))
        if 'processor' in fields:processors.append(fields)
    cpu=[]
    if processors:
        maximum=read('/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq')
        cpu=[dict(name=processors[0].get('model name',platform.machine()),cores=int(processors[0].get('cpu cores',len(processors))),threads=len(processors),maxClockMHz=int(maximum)//1000 if maximum.isdigit() else None)]
    memory=modules()
    visible=re.search(r'^MemTotal:\s+(\d+)',read('/proc/meminfo'),re.M)
    memory_gb=sum(m['capacityGB'] for m in memory) if memory else round(int(visible.group(1))/1024.**2,2) if visible else None
    board=dmi_fields(2);bios=dmi_fields(0)
    disks=[]
    for path in sorted(glob.glob('/sys/block/sd*')+glob.glob('/sys/block/nvme*')+glob.glob('/sys/block/mmcblk*')):
        sectors=read(path+'/size')
        if not sectors.isdigit():continue
        device=os.path.basename(path)
        disks.append(dict(name=(read(path+'/device/model') or ('QNAP eMMC '+device))+' ['+device+']',sizeGB=round(int(sectors)*512/1024.**3,1),
            interface='eMMC' if device.startswith('mmc') else 'NVMe' if device.startswith('nvme') else 'SATA',
            mediaType='eMMC' if device.startswith('mmc') else 'SSD' if read(path+'/queue/rotational')=='0' else 'HDD'))
    gpu=[]
    for line in command(['/bin/lspci']).splitlines():
        if re.search(r'VGA compatible controller|3D controller|Display controller',line,re.I):
            gpu.append(dict(name=line.split(': ',1)[-1],driver='',vramMB=None,virtual=False))
        else:
            pci=re.search(r'Class\s+03[0-9a-fA-F]{2}:\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})',line)
            if pci:
                vendor={'8086':'Intel','10de':'NVIDIA','1002':'AMD'}.get(pci.group(1).lower(),'PCI')
                gpu.append(dict(name=vendor+' display controller (PCI '+pci.group(1)+':'+pci.group(2)+')',driver='',vramMB=None,virtual=False))
    filesystems={};mounts=set()
    for line in read('/proc/mounts').splitlines():
        parts=line.split()
        if len(parts)>=3:
            mount=parts[1].replace('\\040',' ');mounts.add(mount);filesystems[mount]=parts[2]
    volumes=[]
    for line in command(['df','-Pk']).splitlines()[1:]:
        parts=line.split(None,5)
        if len(parts)!=6 or not parts[0].startswith('/dev/'):continue
        try:
            total,used,free=[int(x)*1024 for x in parts[1:4]]
        except ValueError:continue
        volumes.append(dict(drive=parts[5],fileSystem=filesystems.get(parts[5],''),sizeBytes=total,usedBytes=used,freeBytes=free,physical=True,status='not-scanned',tree=None))
    arrays=[]
    for path in sorted(glob.glob('/sys/block/md*/md')):
        device=os.path.basename(os.path.dirname(path));sectors=read(os.path.dirname(path)+'/size')
        members=[os.path.basename(link).replace('dev-','') for link in glob.glob(path+'/dev-*')]
        arrays.append(dict(name=device,level=read(path+'/level'),state=read(path+'/array_state'),members=members,
            sizeBytes=int(sectors)*512 if sectors.isdigit() else None))
    software=[]
    parser=configparser.RawConfigParser()
    parser.read('/etc/config/qpkg.conf')
    for section in parser.sections():
        def option(key):
            try:return parser.get(section,key)
            except (configparser.NoOptionError,configparser.NoSectionError):return ''
        if option('Version'):software.append(dict(name=option('Display_Name') or section,version=option('Version'),publisher=''))
    network=[]
    for path in sorted(glob.glob('/sys/class/net/*')):
        device=os.path.basename(path)
        if device=='lo' or not os.path.isdir(path):continue
        speed=read(path+'/speed')
        network.append(dict(name=device,connected=read(path+'/operstate')=='up',speedMbps=int(speed) if speed.isdigit() else None))
    snapshot=dict(id=uuid.uuid4().hex,capturedAt=now(),maxDepth=4,volumes=volumes)
    for volume in volumes:
        print('Scanning QNAP volume {0} (budget {1}s)...'.format(volume['drive'],seconds),file=sys.stderr)
        tree=scan(volume['drive'],seconds,mounts-set([volume['drive']]))
        volume['tree']=tree;volume['status']='partial' if tree['partial'] or tree['errors'] else 'complete'
    snapshot['completedAt']=now()
    docker_available=bool(command(['which','docker']))
    # This NAS has no Container Station installed; keep uninspected resources unknown.
    docker=dict(available=docker_available,status='unavailable',summary=[],containers=[],images=[],volumes=[],disks=[],warnings=[])
    return dict(schemaVersion=1,id=name,name=name,status='collected',collectedAt=captured,source='QNAP getcfg / DMI / sysfs / QPKG (SSH)',
        hardware=dict(manufacturer='QNAP',model=model,cpu=cpu,memoryGB=memory_gb,memorySource='dmi' if memory else 'os-visible',memory=memory,gpu=gpu,
            motherboard=[dict(manufacturer=board.get('Manufacturer',''),product=board.get('Product Name',''),version=board.get('Version',''))],
            bios=dict(manufacturer=bios.get('Vendor',''),version=bios.get('Version','')),disks=disks,
            volumes=[dict(drive=v['drive'],fileSystem=v['fileSystem'],sizeGB=round(v['sizeBytes']/1024.**3,1),freeGB=round(v['freeBytes']/1024.**3,1)) for v in volumes],network=network),
        os=dict(name='QNAP QTS '+version,version=version,build=build,architecture=platform.machine()),
        nas=dict(model=model,firmwareVersion=version,firmwareBuild=build,kernel=platform.release(),arrays=arrays),
        software=sorted(software,key=lambda x:x['name'].lower()),tools=[dict(name='Python',version=sys.version.split()[0]),dict(name='Linux kernel',version=platform.release())],
        storageSnapshots=[snapshot],subsystems=dict(id=uuid.uuid4().hex,capturedAt=now(),completedAt=now(),wsl=dict(available=False,status='not-applicable',distributions=[]),docker=docker),ai=None,warnings=[])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name',required=True)
    parser.add_argument('--storage-seconds',type=float,default=30)
    args=parser.parse_args()
    print(json.dumps(inventory(args.name,args.storage_seconds),ensure_ascii=True))
