$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::InputEncoding=[Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$OutputEncoding=[Text.UTF8Encoding]::new($false)
$payload=[Console]::In.ReadLine() | ConvertFrom-Json
$temporaryRoot=[IO.Path]::GetFullPath($env:TEMP)
$directory=[IO.Path]::GetFullPath((Join-Path $temporaryRoot ('pc-atlas-'+[guid]::NewGuid().ToString('N'))))
if(!$directory.StartsWith($temporaryRoot.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected temporary directory'}
New-Item -ItemType Directory -Path $directory | Out-Null
$spec=Join-Path $directory 'collect-pc.ps1'
$usage=Join-Path $directory 'collect-usage.py'
$aiScript=Join-Path $directory 'ai-probe.py'
$output=Join-Path $directory 'inventory.json'
$aiOutput=Join-Path $directory 'ai.json'
$runtimeRoot=[IO.Path]::GetFullPath((Join-Path $directory 'python-runtime'))
$runtimeArchive=$null
try{
    [IO.File]::WriteAllText($spec,$payload.spec,[Text.UTF8Encoding]::new($true))
    [IO.File]::WriteAllText($usage,$payload.usage,[Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($aiScript,$payload.ai,[Text.UTF8Encoding]::new($false))
    if($payload.runtimeArchive){
        if($payload.runtimeArchive -notmatch '^\.pc-atlas-python-[a-f0-9]{32}\.zip$'){throw 'Unexpected runtime archive name'}
        $runtimeArchive=Join-Path $env:USERPROFILE $payload.runtimeArchive
        Expand-Archive -LiteralPath $runtimeArchive -DestinationPath $runtimeRoot
        $python=Join-Path $runtimeRoot 'python.exe'
    }else{
        $python=(Get-Command python -ErrorAction Stop).Source
        if($python -like '*\WindowsApps\*'){throw 'Python executable is only a Windows Store alias; provide --python-archive'}
    }
    if($payload.onlyAi){
        [Console]::Error.WriteLine('Inspecting CUDA/PyTorch and installed environment packages...')
        $aiJson=& $python $aiScript
        if($LASTEXITCODE -ne 0){throw 'AI environment collection failed'}
        [Console]::Out.Write(($aiJson -join "`n"))
        return
    }
    [Console]::Error.WriteLine('Reading Windows hardware and installed software...')
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
    & $spec -Name $payload.name -OutputPath $output | Out-Null
    [Console]::Error.WriteLine('Reading Windows WSL/Docker and storage usage...')
    $scanArgs=@($usage,'--computer',$output,'--kind','all','--seconds-per-volume',$payload.seconds,'--skip-ai')
    if($payload.expandOverGB){$scanArgs+=@('--expand-over-gb',$payload.expandOverGB)}
    & $python @scanArgs | Out-Null
    if($LASTEXITCODE -ne 0){throw 'Usage collection failed'}
    [Console]::Error.WriteLine('Inspecting CUDA/PyTorch environments...')
    $aiJson=& $python $aiScript
    if($LASTEXITCODE -ne 0){throw 'AI environment collection failed'}
    [IO.File]::WriteAllText($aiOutput,($aiJson -join "`n"),[Text.UTF8Encoding]::new($false))
    & $python -c "import json,sys; pc=json.load(open(sys.argv[1],encoding='utf-8-sig')); pc['ai']=json.load(open(sys.argv[2],encoding='utf-8-sig')); pc['source']+=' (SSH)'; print(json.dumps(pc))" $output $aiOutput
    if($LASTEXITCODE -ne 0){throw 'Cannot export inventory'}
}finally{
    if($runtimeArchive -and (Test-Path -LiteralPath $runtimeArchive)){Remove-Item -LiteralPath $runtimeArchive -Force}
    if(Test-Path -LiteralPath $runtimeRoot){
        if(!$runtimeRoot.StartsWith($directory.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected runtime cleanup path'}
        Remove-Item -LiteralPath $runtimeRoot -Recurse -Force
    }
    foreach($file in @($spec,$usage,$aiScript,$output,$aiOutput,($output+'.tmp'))){if(Test-Path -LiteralPath $file){Remove-Item -LiteralPath $file -Force}}
    if(Test-Path -LiteralPath $directory){Remove-Item -LiteralPath $directory -Force}
    if($PSCommandPath -and ([IO.Path]::GetFileName($PSCommandPath) -match '^\.pc-atlas-wrapper-[a-f0-9]{32}\.ps1$')){Remove-Item -LiteralPath $PSCommandPath -Force}
}
