"""Run the Linux collector via SSH stdin without installing files remotely."""
import argparse
import json
import os
from pathlib import Path
import re
import base64
import tempfile
import uuid
import subprocess
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--host',required=True)
parser.add_argument('--name',required=True)
parser.add_argument('--output',required=True)
parser.add_argument('--storage-seconds',type=float,default=45)
parser.add_argument('--platform',choices=['linux','windows'],default='linux')
parser.add_argument('--only-ai',action='store_true',help='Refresh only CUDA/PyTorch in an existing Linux record')
args=parser.parse_args()
if not re.fullmatch(r'[a-zA-Z0-9_.@:-]+',args.host) or args.host.startswith('-') or not re.fullmatch(r'[a-zA-Z0-9_-]{1,48}',args.name) or not 0<args.storage_seconds<=600:
    parser.error('Invalid SSH host, computer name or scan budget')
project=Path(__file__).parent
if args.platform=='linux':
    ai_source=(project/'scripts'/'ai-probe.py').read_text(encoding='utf-8')
    if args.only_ai:
        script=ai_source.encode('utf-8')
        remote='python3 -'
    else:
        script=(project/'scripts'/'collect-linux.py').read_text(encoding='utf-8').replace('AI_PROBE_SOURCE = None','AI_PROBE_SOURCE = '+repr(ai_source)).encode('utf-8')
        remote='python3 - --name {0} --storage-seconds {1}'.format(args.name,args.storage_seconds)
else:
    wrapper=(project/'scripts'/'collect-windows-remote.ps1').read_text(encoding='utf-8-sig')
    payload_name='.pc-atlas-'+uuid.uuid4().hex+'.json'
    wrapper=wrapper.replace("$payload=[Console]::In.ReadLine() | ConvertFrom-Json", "$payloadFile=Join-Path $env:USERPROFILE '"+payload_name+"'\n$payload=[IO.File]::ReadAllText($payloadFile) | ConvertFrom-Json\nRemove-Item -LiteralPath $payloadFile -Force")
    remote='powershell.exe -NoProfile -NonInteractive -EncodedCommand '+base64.b64encode(wrapper.encode('utf-16-le')).decode('ascii')
    payload=json.dumps({'name':args.name,'seconds':args.storage_seconds,'onlyAi':args.only_ai,'spec':(project/'collect-pc.ps1').read_text(encoding='utf-8-sig'),'usage':(project/'collect-usage.py').read_text(encoding='utf-8'),'ai':(project/'scripts'/'ai-probe.py').read_text(encoding='utf-8')}).encode('utf-8')
    with tempfile.NamedTemporaryFile(prefix='pc-atlas-',suffix='.json',delete=False) as temporary:
        temporary.write(payload)
        local_payload=Path(temporary.name)
    try:
        subprocess.run(['scp','-q','-o','BatchMode=yes',str(local_payload),args.host+':'+payload_name],check=True,timeout=30)
    finally:
        local_payload.unlink()
    script=b''
process=subprocess.Popen(['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=10',args.host,remote],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
try:
    data,_=process.communicate(input=script,timeout=900)
except subprocess.TimeoutExpired:
    process.kill()
    process.communicate()
    raise SystemExit('SSH inventory timed out; no output was saved')
if process.returncode:
    raise SystemExit('SSH inventory failed; no output was saved')
pc=json.loads(data.decode('utf-8'))
if args.only_ai:
    ai=pc
    pc=json.loads(Path(args.output).read_text(encoding='utf-8-sig'))
    pc['ai']=ai
if pc.get('schemaVersion')!=1 or pc.get('id')!=args.name:
    raise SystemExit('Unexpected remote inventory format')
target=Path(args.output)
target.parent.mkdir(parents=True,exist_ok=True)
temporary=target.with_name(target.name+'.tmp')
temporary.write_text(json.dumps(pc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
os.replace(temporary,target)
print('Saved {0}: {1} packages, {2} containers, {3} image tags'.format(pc['id'],len(pc['software']),len(pc['subsystems']['docker']['containers']),len(pc['subsystems']['docker']['images'])))
