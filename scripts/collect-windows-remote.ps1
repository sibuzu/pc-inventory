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
try{
    [IO.File]::WriteAllText($spec,$payload.spec,[Text.UTF8Encoding]::new($true))
    [IO.File]::WriteAllText($usage,$payload.usage,[Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($aiScript,$payload.ai,[Text.UTF8Encoding]::new($false))
    $python=(Get-Command python -ErrorAction Stop).Source
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
    & $python $usage --computer $output --kind all --seconds-per-volume $payload.seconds --skip-ai | Out-Null
    if($LASTEXITCODE -ne 0){throw 'Usage collection failed'}
    [Console]::Error.WriteLine('Inspecting CUDA/PyTorch environments...')
    $aiJson=& $python $aiScript
    if($LASTEXITCODE -ne 0){throw 'AI environment collection failed'}
    $pc=[IO.File]::ReadAllText($output) | ConvertFrom-Json
    $pc | Add-Member -NotePropertyName ai -NotePropertyValue (($aiJson -join "`n") | ConvertFrom-Json) -Force
    $pc.source+=' (SSH)'
    [Console]::Out.Write(($pc | ConvertTo-Json -Depth 40))
}finally{
    foreach($file in @($spec,$usage,$aiScript,$output,($output+'.tmp'))){if(Test-Path -LiteralPath $file){Remove-Item -LiteralPath $file -Force}}
    if(Test-Path -LiteralPath $directory){Remove-Item -LiteralPath $directory -Force}
}
