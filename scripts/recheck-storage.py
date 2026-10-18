"""Refresh only storage over SSH, preserving the existing PC and environment inventory."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

ROOT=Path(__file__).resolve().parents[1]
WINDOWS_WRAPPER=r'''
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$payloadFile=Join-Path $env:USERPROFILE 'PAYLOAD_NAME'
$payload=[IO.File]::ReadAllText($payloadFile) | ConvertFrom-Json
Remove-Item -LiteralPath $payloadFile -Force
$temporaryRoot=[IO.Path]::GetFullPath($env:TEMP)
$directory=[IO.Path]::GetFullPath((Join-Path $temporaryRoot ('pc-atlas-storage-'+[guid]::NewGuid().ToString('N'))))
if(!$directory.StartsWith($temporaryRoot.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected temporary directory'}
New-Item -ItemType Directory -Path $directory | Out-Null
$usage=Join-Path $directory 'collect-usage.py'
$output=Join-Path $directory 'storage.json'
try{
    [IO.File]::WriteAllText($usage,$payload.usage,[Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($output,'{"schemaVersion":1,"hardware":{}}',[Text.UTF8Encoding]::new($false))
    $python=(Get-Command python -ErrorAction Stop).Source
    $scanArgs=@('-u',$usage,'--computer',$output,'--kind','storage','--seconds-per-volume',$payload.seconds,'--depth','4')
    if($payload.expandOverGB){$scanArgs+=@('--expand-over-gb',$payload.expandOverGB)}
    & $python @scanArgs | ForEach-Object {[Console]::Error.WriteLine($_)}
    if($LASTEXITCODE -ne 0){throw 'Storage scan failed'}
    & $python -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1],encoding='utf-8-sig'))['storageSnapshots'][0]))" $output
    if($LASTEXITCODE -ne 0){throw 'Cannot export storage snapshot'}
}finally{
    foreach($file in @($usage,$output,($output+'.tmp'))){if(Test-Path -LiteralPath $file){Remove-Item -LiteralPath $file -Force}}
    if(Test-Path -LiteralPath $directory){Remove-Item -LiteralPath $directory -Force}
}
'''

LINUX_PROBE=r'''
volumes=[]
for line in command(['df','-PT','-B1']).splitlines()[1:]:
    parts=line.split(None,6)
    if len(parts)!=7 or not parts[0].startswith('/dev/'):continue
    volumes.append(dict(drive=parts[6],fileSystem=parts[1],sizeBytes=int(parts[2]),usedBytes=int(parts[3]),freeBytes=int(parts[4]),physical=True,tree=None,status='not-scanned'))
mounts=storage_mounts()
snapshot=dict(id=uuid.uuid4().hex,capturedAt=now(),maxDepth=64 if EXPAND_THRESHOLD else 4,volumes=volumes)
if EXPAND_THRESHOLD:
    snapshot['expandThresholdBytes']=EXPAND_THRESHOLD
    snapshot['optionalDetailLevels']=1
for volume in volumes:
    print('Scanning {0}, budget {1}s'.format(volume['drive'],STORAGE_SECONDS),file=sys.stderr,flush=True)
    started=time.monotonic()
    tree=scan_tree(volume['drive'],STORAGE_SECONDS,mounts-set([volume['drive']]),max_depth=snapshot['maxDepth'],expand_threshold=EXPAND_THRESHOLD)
    tree['durationSeconds']=round(time.monotonic()-started,2)
    volume['tree']=tree
    volume['status']='partial' if tree['partial'] or tree['errors'] else 'complete'
    print('Finished {0}: bytes={1}, files={2}, timedOut={3}, errors={4}'.format(volume['drive'],tree['bytes'],tree['files'],tree['partial'],tree['errors']),file=sys.stderr,flush=True)
snapshot['completedAt']=now()
print(json.dumps(snapshot,ensure_ascii=True))
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name',required=True)
    parser.add_argument('--host',required=True)
    parser.add_argument('--platform',choices=['windows','linux'],required=True)
    parser.add_argument('--seconds',type=int,default=600)
    parser.add_argument('--expand-over-gb',type=float)
    parser.add_argument('--sudo',action='store_true',help='Use existing noninteractive sudo for read-only Linux storage collection')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,48}',args.name) or not re.fullmatch(r'[a-zA-Z0-9_.@:-]+',args.host) or args.host.startswith('-') or not 1<=args.seconds<=3600:
        parser.error('Invalid name, host or budget')
    if args.expand_over_gb is not None and not 0 < args.expand_over_gb <= 1048576:
        parser.error('Invalid expansion threshold')
    pc=json.loads((ROOT/'dist'/'data'/(args.name+'.json')).read_text(encoding='utf-8'))
    if args.expand_over_gb is None and pc.get('storageSnapshots'):
        threshold=pc['storageSnapshots'][-1].get('expandThresholdBytes')
        if threshold:args.expand_over_gb=threshold/1024**3
    if args.platform=='windows':
        name='.pc-atlas-storage-'+uuid.uuid4().hex+'.json'
        payload=json.dumps(dict(seconds=args.seconds,expandOverGB=args.expand_over_gb,usage=(ROOT/'collect-usage.py').read_text(encoding='utf-8'))).encode('utf-8')
        with tempfile.NamedTemporaryFile(prefix='pc-atlas-storage-',suffix='.json',delete=False) as temp:
            temp.write(payload);local=Path(temp.name)
        try:
            subprocess.run(['scp','-q','-o','BatchMode=yes',str(local),args.host+':'+name],check=True,timeout=40)
        finally:local.unlink()
        wrapper=WINDOWS_WRAPPER.replace('PAYLOAD_NAME',name)
        command_line='powershell.exe -NoProfile -NonInteractive -EncodedCommand '+base64.b64encode(wrapper.encode('utf-16-le')).decode('ascii')
        script=b''
    else:
        source=(ROOT/'scripts'/'collect-linux.py').read_text(encoding='utf-8')
        threshold=int(args.expand_over_gb*1024**3) if args.expand_over_gb is not None else None
        script=(source.split("if __name__=='__main__':")[0]+'\nSTORAGE_SECONDS='+str(args.seconds)+'\nEXPAND_THRESHOLD='+repr(threshold)+'\n'+LINUX_PROBE).encode('utf-8')
        command_line='sudo -n python3 -' if args.sudo else 'python3 -'
    process=subprocess.Popen(['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=10',args.host,command_line],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    try:
        data,_=process.communicate(script,timeout=args.seconds*16+180)
    except subprocess.TimeoutExpired:
        process.kill();process.communicate();raise SystemExit('SSH storage scan timed out; no result saved')
    if process.returncode:raise SystemExit('SSH storage scan failed; no result saved')
    snapshot=json.loads(data.decode('utf-8-sig'))
    if not snapshot.get('volumes'):raise SystemExit('No storage volumes returned')
    pc['storageSnapshots']=(pc.get('storageSnapshots',[])+[snapshot])[-20:]
    pc['hardware']['volumes']=[dict(drive=v['drive'],fileSystem=v['fileSystem'],sizeGB=round(v['sizeBytes']/1024**3,1),freeGB=round(v['freeBytes']/1024**3,1)) for v in snapshot['volumes']]
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.name+'.tmp')
    temp.write_text(json.dumps(pc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(temp,target)
    print('Saved {0}: {1} volumes'.format(args.name,len(snapshot['volumes'])),flush=True)

if __name__=='__main__':main()
