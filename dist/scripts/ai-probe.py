"""Read-only CUDA/PyTorch inventory. Compatible with Python 2.7 and 3.4+."""
from __future__ import print_function
import glob
import json
import os
import re
import subprocess
import sys
import time

PROBE = r'''
from __future__ import print_function
import json,sys,glob,os
sys.path=[p for p in sys.path if p and p!='.']
r={'python':sys.version.split()[0],'prefix':sys.prefix,'torchVersion':'','torchCuda':'','cudnn':None,'cudaAvailable':None,'deviceCount':None,'error':'','packages':[]}
packages={}
try:
    import importlib.metadata as metadata
    for d in metadata.distributions():
        name=d.metadata.get('Name')
        if name:packages[(name.lower().replace('_','-'),str(d.version))]={'name':name,'version':str(d.version),'source':'python','build':''}
except ImportError:
    try:
        import pkg_resources
        for d in pkg_resources.working_set:packages[(d.project_name.lower().replace('_','-'),str(d.version))]={'name':d.project_name,'version':str(d.version),'source':'python','build':''}
    except Exception:pass
except Exception:pass
for filename in glob.glob(os.path.join(sys.prefix,'conda-meta','*.json')):
    try:
        with open(filename) as handle:d=json.load(handle)
        name=d['name'];version=str(d['version'])
        packages[(name.lower().replace('_','-'),version)]={'name':name,'version':version,'source':'conda','build':str(d.get('build',''))}
    except Exception:pass
r['packages']=sorted(packages.values(),key=lambda d:d['name'].lower())
try:
    import torch
    r['torchVersion']=str(torch.__version__)
    r['torchCuda']=str(getattr(getattr(torch,'version',None),'cuda','') or '')
    try:r['cudnn']=torch.backends.cudnn.version()
    except Exception:pass
    try:
        r['cudaAvailable']=bool(torch.cuda.is_available())
        if r['cudaAvailable']:r['deviceCount']=int(torch.cuda.device_count())
    except Exception as e:r['error']=type(e).__name__+': '+str(e)[:350]
except ImportError:r['error']='PyTorch not installed or unavailable to this interpreter'
except Exception as e:r['error']=type(e).__name__+': '+str(e)[:350]
print(json.dumps(r))
'''


def execute(args, timeout=25):
    try:
        options=dict(stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if os.name=='nt':options['creationflags']=0x08000000
        process=subprocess.Popen(args,**options)
        if sys.version_info >= (3,3):
            try:stdout,stderr=process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill();process.communicate();return '', 'Timed out'
        else:
            # Python 2.7 is supported for the probe payload; collectors run on 3.4+.
            stdout,stderr=process.communicate()
        return stdout.decode('utf-8','replace').strip(),stderr.decode('utf-8','replace').strip()
    except OSError:return '', 'Command unavailable'


def collect_ai():
    result=dict(collectedAt=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),driverVersion='',driverCuda='',toolkits=[],environments=[],warnings=[])
    gpu,_=execute(['nvidia-smi','--query-gpu=driver_version','--format=csv,noheader'])
    result['driverVersion']=gpu.splitlines()[0] if gpu else ''
    header,_=execute(['nvidia-smi'],timeout=10)
    match=re.search(r'CUDA Version:\s*([0-9.]+)',header)
    if match:result['driverCuda']=match.group(1)
    nvcc_paths=['nvcc']
    if os.name=='nt':
        roots=glob.glob(os.path.join(os.environ.get('ProgramFiles',r'C:\Program Files'),'NVIDIA GPU Computing Toolkit','CUDA','v*'))
        for root in roots:nvcc_paths.append(os.path.join(root,'bin','nvcc.exe'))
        if os.environ.get('CUDA_PATH'):nvcc_paths.append(os.path.join(os.environ['CUDA_PATH'],'bin','nvcc.exe'))
    else:
        roots=glob.glob('/usr/local/cuda*')+glob.glob('/opt/cuda*')
        nvcc_paths.extend(os.path.join(root,'bin','nvcc') for root in roots)
    toolkits={}
    for path in nvcc_paths:
        output,_=execute([path,'--version'],timeout=8)
        match=re.search(r'release\s+([0-9.]+)',output)
        if match:toolkits[match.group(1)]=dict(version=match.group(1),source='nvcc',path=path)
    # Preserve detected install-directory versions when nvcc is not executable.
    for root in roots:
        match=re.search(r'(?:cuda[-_]?|v)(\d+(?:\.\d+)+)$',root,re.I)
        if match and match.group(1) not in toolkits:
            toolkits[match.group(1)]=dict(version=match.group(1),source='installation-directory',path=root)
    result['toolkits']=sorted(toolkits.values(),key=lambda item:item['version'])
    candidates=[sys.executable,'python','python3','python2']
    home=os.path.expanduser('~')
    bases=[os.path.join(home,name) for name in ('anaconda3','miniconda3','anaconda2','miniconda2','miniforge3')]
    if os.name=='nt':bases.extend([os.path.join(os.environ.get('ProgramData',r'C:\ProgramData'),name) for name in ('anaconda3','miniconda3')])
    for base in bases:
        candidates.append(os.path.join(base,'python.exe' if os.name=='nt' else 'bin/python'))
        candidates.extend(glob.glob(os.path.join(base,'envs','*','python.exe' if os.name=='nt' else 'bin/python')))
    envfile=os.path.join(home,'.conda','environments.txt')
    try:
        with open(envfile) as handle:
            for line in handle:
                if line.strip():candidates.append(os.path.join(line.strip(),'python.exe' if os.name=='nt' else 'bin/python'))
    except IOError:pass
    candidates.extend(glob.glob(os.path.join(home,'.virtualenvs','*','Scripts/python.exe' if os.name=='nt' else 'bin/python')))
    seen=set()
    for candidate in list(dict.fromkeys(candidates))[:50]:
        if os.name=='nt':
            possible=[candidate] if os.path.isabs(candidate) else [os.path.join(folder,candidate+suffix) for folder in os.environ.get('PATH','').split(os.pathsep) for suffix in ('.exe','')]
            found=next((path for path in possible if os.path.isfile(path)),None)
            if not found or 'windowsapps' in found.lower():continue
            candidate=found
        output,error=execute([candidate,'-c',PROBE],timeout=30)
        try:record=json.loads(output.splitlines()[-1])
        except (ValueError,IndexError):
            if error!='Command unavailable':result['warnings'].append('Unable to probe interpreter: '+os.path.basename(candidate))
            continue
        identity=(record['prefix'],record['python'])
        if identity in seen:continue
        seen.add(identity)
        record.update(name=os.path.basename(record.pop('prefix').rstrip('\\/')) or 'system',scope='host',interpreter=candidate)
        result['environments'].append(record)
    # Query only running containers; never start or modify containers/images.
    ids,_=execute(['docker','ps','--format','{{.ID}}\t{{.Names}}'],timeout=10)
    for line in ids.splitlines():
        parts=line.split('\t',1)
        if len(parts)!=2:continue
        container_id,container_name=parts
        observed=set()
        for interpreter in ('python','python3'):
            output,error=execute(['docker','exec',container_id,interpreter,'-c',PROBE],timeout=30)
            try:record=json.loads(output.splitlines()[-1])
            except (ValueError,IndexError):continue
            identity=(record['prefix'],record['python'])
            if identity in observed:continue
            observed.add(identity)
            record.update(name=container_name+' / '+(os.path.basename(record.pop('prefix').rstrip('/')) or 'system'),scope='container',interpreter=interpreter)
            result['environments'].append(record)
        if not observed:result['warnings'].append('Python/PyTorch could not be inspected in running container '+container_name)
    result['warnings'].append('Scope: PATH Python, common Conda installations, registered Conda environments, ~/.virtualenvs and Python in running containers. Stopped containers and unregistered project venvs are not started or scanned.')
    return result


if __name__=='__main__':
    print(json.dumps(collect_ai(),ensure_ascii=True))
