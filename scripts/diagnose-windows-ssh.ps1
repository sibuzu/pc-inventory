param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-zA-Z0-9_.-]+$')][string]$ComputerName,
    [ValidatePattern('^[a-zA-Z0-9_.-]+$')][string]$UserName='jack'
)
$ErrorActionPreference='Stop'
$script=@'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
'=== REMOTE IDENTITY ==='
hostname.exe
whoami.exe
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
'ADMIN GROUP SID PRESENT: '+(@($identity.Groups | ForEach-Object {$_.Value}) -contains 'S-1-5-32-544')
'=== ACTIVE CONFIG LINES ==='
Get-Content "$env:ProgramData\ssh\sshd_config" | Where-Object {$_ -match '^\s*(PubkeyAuthentication|AuthorizedKeysFile|AuthenticationMethods|Match|Include|StrictModes)\b'}
'=== KEY FILES: ACL / ENCODING / FINGERPRINTS ==='
foreach($file in @("$env:ProgramData\ssh\administrators_authorized_keys","$env:USERPROFILE\.ssh\authorized_keys")){
 $file
 if(!(Test-Path -LiteralPath $file)){'NOT FOUND';continue}
 try{
  $acl=Get-Acl -LiteralPath $file -ErrorAction Stop
  'OWNER SID: '+$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
  'ACL SDDL: '+$acl.Sddl
  $raw=[IO.File]::ReadAllBytes($file)
  'FIRST BYTES: '+[BitConverter]::ToString($raw,0,[Math]::Min(8,$raw.Length))
  $text=[IO.File]::ReadAllText($file)
  if($text -match '\A\s*(ssh-(rsa|ed25519)|ecdsa-sha2-nistp\d+)\s' -and $text -notmatch '[\x00-\x08\x0B\x0C\x0E-\x1F\uFFFD]'){
   & "$env:WINDIR\System32\OpenSSH\ssh-keygen.exe" -lf $file 2>&1
  }else{'Fingerprint skipped: file does not begin with a plain-text SSH public key.'}
 }catch{$_.Exception.Message}
}
'=== DONE ==='
'@
$script=$script.Replace('DIAG_USERNAME',$UserName)
$encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
if($encoded.Length -gt 7800){throw 'Diagnostic command exceeds the Windows command-line limit'}
$directory=Join-Path (Split-Path -Parent $PSScriptRoot) '.sites-runtime'
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$reportPath=Join-Path $directory ('ssh-diagnostics-'+$ComputerName+'.txt')
$writer=[IO.StreamWriter]::new($reportPath,$false,[Text.UTF8Encoding]::new($false))
$writer.AutoFlush=$true
try{
 $writer.WriteLine('=== LOCAL PUBLIC KEY ===')
 & ssh-keygen -lf (Join-Path $env:USERPROFILE '.ssh\id_rsa.pub') | ForEach-Object {$writer.WriteLine([string]$_); Write-Host $_}
 & ssh -o ConnectTimeout=5 "$UserName@$ComputerName" "powershell.exe -NoProfile -NonInteractive -OutputFormat Text -EncodedCommand $encoded" | ForEach-Object {$writer.WriteLine([string]$_); Write-Host $_}
}finally{$writer.Dispose()}
Write-Host ('Saved diagnostic report: '+$reportPath)
