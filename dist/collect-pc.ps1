param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-zA-Z0-9_-]{1,48}$')][string]$Name,
    [string]$OutputPath = (Join-Path $PSScriptRoot "$Name.json")
)
$ErrorActionPreference = 'Stop'
$warnings = [System.Collections.Generic.List[string]]::new()
function Read-Cim($Class) {
    try { @(Get-CimInstance -ClassName $Class -ErrorAction Stop) }
    catch { $warnings.Add("無法讀取 $Class"); @() }
}
$os = @(Read-Cim 'Win32_OperatingSystem') | Select-Object -First 1
$system = @(Read-Cim 'Win32_ComputerSystem') | Select-Object -First 1
$bios = @(Read-Cim 'Win32_BIOS') | Select-Object -First 1
$cpus = @(Read-Cim 'Win32_Processor' | ForEach-Object {
    [ordered]@{name=$_.Name.Trim();cores=$_.NumberOfCores;threads=$_.NumberOfLogicalProcessors;maxClockMHz=$_.MaxClockSpeed}
})
$ram = @(Read-Cim 'Win32_PhysicalMemory' | ForEach-Object {
    [ordered]@{capacityGB=[math]::Round($_.Capacity/1GB,2);speedMHz=$_.Speed;configuredMHz=$_.ConfiguredClockSpeed;manufacturer=$_.Manufacturer.Trim();partNumber=$_.PartNumber.Trim();slot=$_.DeviceLocator}
})
$gpuDetails = @{}
try {
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        $rows = & nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits 2>$null
        if ($LASTEXITCODE -eq 0) {
            foreach ($row in $rows) { $parts=$row -split ',\s*'; if ($parts.Count -ge 3) { $gpuDetails[$parts[0].Trim()]=@{vramMB=[double]$parts[1];driver=$parts[2].Trim()} } }
        }
    }
} catch { $warnings.Add('NVIDIA 詳細資料無法讀取') }
$gpus = @(Read-Cim 'Win32_VideoController' | ForEach-Object {
    $entry=[ordered]@{name=$_.Name;driver=$_.DriverVersion;vramMB=$null;virtual=($_.Name -match 'Remote|Indirect|Virtual')}
    if ($gpuDetails.ContainsKey($_.Name)) { $entry.vramMB=$gpuDetails[$_.Name].vramMB; $entry.driver=$gpuDetails[$_.Name].driver }
    $entry
})
$disks = @(Read-Cim 'Win32_DiskDrive' | ForEach-Object {
    [ordered]@{name=$_.Model.Trim();sizeGB=[math]::Round($_.Size/1GB,1);interface=$_.InterfaceType;mediaType=$_.MediaType}
})
$volumes = @(Read-Cim 'Win32_LogicalDisk' | Where-Object DriveType -EQ 3 | ForEach-Object {
    [ordered]@{drive=$_.DeviceID;fileSystem=$_.FileSystem;sizeGB=[math]::Round($_.Size/1GB,1);freeGB=[math]::Round($_.FreeSpace/1GB,1)}
})
$boards = @(Read-Cim 'Win32_BaseBoard' | ForEach-Object { [ordered]@{manufacturer=$_.Manufacturer;product=$_.Product;version=$_.Version} })
$networks = @(Read-Cim 'Win32_NetworkAdapter' | Where-Object PhysicalAdapter | ForEach-Object {
    [ordered]@{name=$_.Name;connected=($_.NetConnectionStatus -eq 2);speedMbps=if ($_.Speed -and $_.Speed -lt 1e13) { [math]::Round($_.Speed/1e6) } else { $null }}
})
$registryPaths = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*')
$software = @(Get-ItemProperty -Path $registryPaths -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -and !$_.SystemComponent } | ForEach-Object {
    [pscustomobject]@{name=$_.DisplayName.Trim();version=[string]$_.DisplayVersion;publisher=[string]$_.Publisher}
} | Sort-Object name,version -Unique)
$tools = @()
foreach ($tool in @(@{name='Node.js';command='node';args=@('--version')},@{name='Python';command='python';args=@('--version')},@{name='Git';command='git';args=@('--version')},@{name='Docker';command='docker';args=@('--version')},@{name='CUDA compiler';command='nvcc';args=@('--version')})) {
    if (Get-Command $tool.command -ErrorAction SilentlyContinue) {
        try { $value = & $tool.command @($tool.args) 2>$null; if ($LASTEXITCODE -eq 0) { $tools += [ordered]@{name=$tool.name;version=(@($value) -join ' ').Trim()} } } catch {}
    }
}
$result = [ordered]@{
    schemaVersion=1;id=$Name;name=$Name;status='collected';collectedAt=[DateTimeOffset]::Now.ToString('o');source='Windows CIM / 登錄檔 / 本機命令';
    hardware=[ordered]@{manufacturer=$system.Manufacturer;model=$system.Model;cpu=$cpus;memoryGB=[math]::Round(($ram | ForEach-Object { $_.capacityGB } | Measure-Object -Sum).Sum,2);memory=$ram;gpu=$gpus;motherboard=$boards;bios=[ordered]@{manufacturer=$bios.Manufacturer;version=$bios.SMBIOSBIOSVersion};disks=$disks;volumes=$volumes;network=$networks};
    os=[ordered]@{name=$os.Caption;version=$os.Version;build=$os.BuildNumber;architecture=$os.OSArchitecture};software=$software;tools=$tools;warnings=@($warnings)
}
$target = [IO.Path]::GetFullPath($OutputPath)
$parent = Split-Path -Parent $target
if (!(Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
$existing = $null
if (Test-Path -LiteralPath $target) {
    try { $existing = Get-Content -LiteralPath $target -Raw -Encoding UTF8 | ConvertFrom-Json } catch {}
}
if ($existing -and $existing.id -eq $Name) {
    if ($existing.storageSnapshots) { $result.storageSnapshots = @($existing.storageSnapshots) }
    if ($existing.subsystems) { $result.subsystems = $existing.subsystems }
}
$json = $result | ConvertTo-Json -Depth 40
[IO.File]::WriteAllText($target,$json,[Text.UTF8Encoding]::new($false))
Write-Output "已擷取 $Name，軟體 $($software.Count) 筆，儲存至 $target"
