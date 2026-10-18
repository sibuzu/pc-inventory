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
$config=@(Get-Content "$env:ProgramData\ssh\sshd_config" | Where-Object {$_ -match '^\s*\S' -and $_ -notmatch '^\s*#'})
if(!($config -match '^\s*(Match|Include)\b') -and ($config -match '^\s*AuthorizedKeysFile\s+\.ssh/authorized_keys\s*(#.*)?$')){$admin=$false}
$file=if($admin){Join-Path $env:ProgramData 'ssh\administrators_authorized_keys'}else{Join-Path $env:USERPROFILE '.ssh\authorized_keys'}
'Target key file: '+$file
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $file) | Out-Null
if(!(Test-Path -LiteralPath $file)){New-Item -ItemType File -Path $file | Out-Null}
if($admin){
    takeown.exe /F $file /A | Out-Null
    if($LASTEXITCODE -ne 0){throw 'Target administrator rights required'}
    icacls.exe $file /reset | Out-Null
    if($LASTEXITCODE -ne 0){throw 'Key-file ACL reset failed'}
    icacls.exe $file /inheritance:r /grant:r '*S-1-5-32-544:F' '*S-1-5-18:F'
}else{
    $sid=$identity.User.Value
    $acl=[Security.AccessControl.FileSecurity]::new()
    $acl.SetOwner($identity.User)
    $acl.SetAccessRuleProtection($true,$false)
    foreach($s in @($sid,'S-1-5-18','S-1-5-32-544')){
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($s),'FullControl','Allow'))
    }
    Set-Acl -LiteralPath $file -AclObject $acl
}
if($admin -and $LASTEXITCODE -ne 0){throw 'Key-file ACL repair failed'}
$text=[IO.File]::ReadAllText($file)
if($text -match '[\x00-\x08\x0B\x0C\x0E-\x1F\uFFFD]'){throw "Invalid key-file encoding: $file; file preserved"}
if(!($text -split '\r?\n' | Where-Object {$_.Trim() -eq $key})){
    [IO.File]::WriteAllText($file,$text.TrimEnd()+"`r`n"+$key+"`r`n",[Text.UTF8Encoding]::new($false))
}
'Public key authorized.'
'@
$script=$script.Replace('PUBLIC_KEY_BASE64',$key64)
$encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
if($encoded.Length -gt 7800){throw 'Authorization command exceeds Windows command-line limit'}
& ssh "$UserName@$ComputerName" "powershell.exe -NoProfile -NonInteractive -OutputFormat Text -EncodedCommand $encoded"
if($LASTEXITCODE -ne 0){throw 'Remote key authorization failed'}
& ssh -o BatchMode=yes "$UserName@$ComputerName" 'echo SSH_OK'
if($LASTEXITCODE -ne 0){throw 'Public-key login verification failed'}
