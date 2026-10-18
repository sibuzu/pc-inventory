param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-zA-Z0-9_.:-]+$')][string]$ComputerName,
    [ValidatePattern('^[a-zA-Z0-9_.-]+$')][string]$UserName='jack',
    [string]$PublicKeyPath=(Join-Path $env:USERPROFILE '.ssh\id_rsa.pub')
)
$ErrorActionPreference='Stop'
$key=(Get-Content -LiteralPath $PublicKeyPath -Raw).Trim()
if($key -notmatch '^(ssh-(rsa|ed25519)|ecdsa-sha2-nistp(256|384|521))\s+[A-Za-z0-9+/]+=*(\s[^\r\n]*)?$'){
    throw 'Expected a single SSH public key, not a private key.'
}
$key64=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($key))
$script=@'
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$key=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('PUBLIC_KEY_BASE64'))
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$admin=(@($identity.Groups | ForEach-Object {$_.Value}) -contains 'S-1-5-32-544')
$file=if($admin){Join-Path $env:ProgramData 'ssh\administrators_authorized_keys'}else{Join-Path $env:USERPROFILE '.ssh\authorized_keys'}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $file) | Out-Null
if(!(Test-Path -LiteralPath $file)){New-Item -ItemType File -Path $file | Out-Null}
if($admin){
    takeown.exe /F $file /A | Out-Null
    if($LASTEXITCODE -ne 0){throw 'Administrator rights are required on the target PC to repair the SSH key file. Open PowerShell as Administrator on that PC.'}
    icacls.exe $file /reset | Out-Null
    if($LASTEXITCODE -ne 0){throw 'Could not reset the SSH key-file ACL. Use an elevated PowerShell on the target PC.'}
    icacls.exe $file /inheritance:r /grant:r '*S-1-5-32-544:F' '*S-1-5-18:F'
}else{
    $sid=$identity.User.Value
    icacls.exe $file /inheritance:r /grant:r "*${sid}:F" '*S-1-5-18:F'
}
if($LASTEXITCODE -ne 0){throw 'Cannot repair the key-file ACL through this SSH session. On the target PC, open PowerShell as Administrator and repair administrators_authorized_keys permissions first.'}
if(!(Select-String -LiteralPath $file -SimpleMatch -Pattern $key -Quiet)){
    Add-Content -LiteralPath $file -Value ("`r`n"+$key) -Encoding ascii
}
'Public key authorized.'
'@
$script=$script.Replace('PUBLIC_KEY_BASE64',$key64)
$encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
& ssh "$UserName@$ComputerName" "powershell.exe -NoProfile -EncodedCommand $encoded"
if($LASTEXITCODE -ne 0){throw 'Remote key authorization failed'}
& ssh -o BatchMode=yes "$UserName@$ComputerName" 'echo SSH_OK'
if($LASTEXITCODE -ne 0){throw 'Public-key login verification failed'}
