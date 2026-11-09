# Runs INSIDE Windows Sandbox, at logon (tools/msix/make_sandbox_test.py
# writes the .wsb that starts it). The Windows App Certification Kit on the
# package to ship, as Partner Center runs it, in a Windows that vanishes
# afterwards. Only C:\out leaves the sandbox: out\wack\ holds wack.txt (this
# log, a line a minute while the kit runs, then one per test), the kit's own
# wack_report.xml and console output, and its logs.
#
# The kit is the SDK's, copied in from read-only folders to where the SDK
# installs it, with what it needs beside it: its test engine (TAEF),
# Windows' metadata, the API contracts and the platform list; its COM
# classes are imported from .reg files make_sandbox_test.py read from this
# computer's registry. Each was found missing by a run without it.
#
# The first line refuses anywhere but the sandbox, as sandbox_test.ps1's
# does: on this computer the kit would trust a test certificate, install
# the package and start the app, which would open the owner's notebook.

if ($env:USERNAME -ne 'WDAGUtilityAccount' -or $PSCommandPath -ne 'C:\pkg\sandbox_wack.ps1') { Write-Output 'sandbox_wack.ps1 runs only inside Windows Sandbox: double-click the .wsb that tools/msix/make_sandbox_test.py writes.'; exit 2 }

$ErrorActionPreference = 'Continue'
$results = 'C:\out\wack'
New-Item -ItemType Directory -Force $results | Out-Null
$log = Join-Path $results 'wack.txt'
$utf8 = New-Object System.Text.UTF8Encoding $false
[IO.File]::WriteAllText($log, '', $utf8)
function Log($m) { [IO.File]::AppendAllText($log, ((Get-Date -Format 'HH:mm:ss') + '  ' + $m + "`r`n"), $utf8) }
function Finish {
    Log '== done. The sandbox can be closed.'
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show('The test has finished. You can close Windows Sandbox now.', 'Note Organizer test') | Out-Null
    exit
}

$os = Get-CimInstance Win32_OperatingSystem
Log ("== start: Windows {0}, memory {1} MB, free {2} MB" -f $os.Version, [int]((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1MB), [int]($os.FreePhysicalMemory / 1KB))

# 1. The kit and what it needs, where the SDK puts them.
$root = 'C:\Program Files (x86)\Windows Kits\10'
New-Item -ItemType Directory -Force $root | Out-Null
foreach ($part in @(('C:\kitsrc', 'App Certification Kit'), ('C:\testingsrc', 'Testing'),
        ('C:\unionsrc', 'UnionMetadata'), ('C:\referencessrc', 'References'), ('C:\platformssrc', 'Platforms'))) {
    Copy-Item $part[0] (Join-Path $root $part[1]) -Recurse -Force
}
$kit = Join-Path $root 'App Certification Kit'
foreach ($key in @('HKLM:\SOFTWARE\Microsoft\Windows Kits\Installed Roots',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows Kits\Installed Roots')) {
    New-Item -Force $key | Out-Null
    New-ItemProperty -Path $key -Name KitsRoot10 -Value ($root + '\') -PropertyType String -Force | Out-Null
}
$sdks = 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Microsoft SDKs\Windows\v10.0'
New-Item -Force $sdks | Out-Null
New-ItemProperty -Path $sdks -Name InstallationFolder -Value ($root + '\') -PropertyType String -Force | Out-Null
$version = @(Get-ChildItem (Join-Path $root 'Platforms\UAP') -Directory | Sort-Object { [version]$_.Name })[-1].Name
New-ItemProperty -Path $sdks -Name ProductVersion -Value ($version -replace '\.0$', '') -PropertyType String -Force | Out-Null
$wack = 'HKLM:\SOFTWARE\Microsoft\Windows App Certification Kit'
New-Item -Force $wack | Out-Null
New-ItemProperty -Path $wack -Name InstallLocation -Value ($kit + '\') -PropertyType String -Force | Out-Null
New-ItemProperty -Path $wack -Name FirstRun -Value '1' -PropertyType String -Force | Out-Null
$imported = 0
$regs = @(Get-ChildItem C:\pkg\wack_reg\*.reg)
foreach ($f in $regs) {
    & reg.exe import $f.FullName 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $imported++ } else { Log "reg import FAILED $($f.Name)" }
}
$appcert = Join-Path $kit 'appcert.exe'
Log "kit: $(Test-Path $appcert); TAEF: $(Test-Path (Join-Path $root 'Testing\Runtimes\TAEF\x64\TE.exe')); SDK $version; COM keys imported: $imported of $($regs.Count)"

# 2. The package to ship (the lower of the pair), signed here.
New-Item -ItemType Directory -Force C:\work | Out-Null
$cert = New-SelfSignedCertificate -Type Custom -Subject 'CN=NoteOrganizerTest' -KeyUsage DigitalSignature `
    -FriendlyName 'NoteOrganizer test' -CertStoreLocation 'Cert:\CurrentUser\My' `
    -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3', '2.5.29.19={text}')
Export-Certificate -Cert $cert -FilePath C:\work\test.cer | Out-Null
Import-Certificate -FilePath C:\work\test.cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople | Out-Null
$v = @(Get-ChildItem C:\pkg\NoteOrganizer_*.msix |
    ForEach-Object { $_.BaseName.Substring('NoteOrganizer_'.Length) } |
    Sort-Object { [version]$_ })[0]
$msix = "C:\work\NoteOrganizer_$v.msix"
Copy-Item "C:\pkg\NoteOrganizer_$v.msix" C:\work\
$out = & C:\sdk\signtool.exe sign /fd SHA256 /sha1 $cert.Thumbprint $msix 2>&1
Log "signed $v : exit $LASTEXITCODE"

# 3. The kit: reset, then the test, heard from once a minute.
$out = & $appcert reset 2>&1
Log "appcert reset: exit $LASTEXITCODE $($out | Select-Object -Last 1)"
$report = Join-Path $results 'wack_report.xml'
$console = Join-Path $results 'wack_console.txt'
$p = Start-Process -FilePath $appcert -ArgumentList @('test', '-appxpackagepath', $msix, '-reportoutputpath', $report) `
    -RedirectStandardOutput $console -RedirectStandardError (Join-Path $results 'wack_errors.txt') -PassThru -NoNewWindow
$null = $p.Handle   # held now, or ExitCode reads empty once it ends
$started = Get-Date
while (-not $p.WaitForExit(60000)) {
    $mins = [int]((Get-Date) - $started).TotalMinutes
    Log "appcert running, $mins min: $(Get-Content $console -Tail 1 -ErrorAction SilentlyContinue)"
    if ($mins -ge 50) { Log 'appcert still running after 50 minutes: stopped'; $p | Stop-Process -Force; Finish }
}
$p.WaitForExit()
Log "appcert test: exit $($p.ExitCode) after $([int]((Get-Date) - $started).TotalMinutes) min"

# The kit's own logs, small files only, for a run that went wrong.
$kitlogs = Join-Path $env:LOCALAPPDATA 'Microsoft\AppCertKit'
if (Test-Path $kitlogs) {
    New-Item -ItemType Directory -Force (Join-Path $results 'kitlogs') | Out-Null
    Get-ChildItem $kitlogs -Recurse -File -Include *.xml, *.log, *.txt |
        Where-Object { $_.Length -lt 5MB } | Copy-Item -Destination (Join-Path $results 'kitlogs') -Force
}

# 4. What it found: the overall result, then every test.
if (-not (Test-Path $report)) { Log 'NO REPORT written'; Finish }
[xml]$x = Get-Content $report -Raw -Encoding UTF8
Log "OVERALL: $($x.REPORT.OVERALL_RESULT)"
foreach ($t in $x.SelectNodes('//TEST')) {
    $result = $t.SelectSingleNode('RESULT').InnerText
    $optional = if ($t.OPTIONAL -eq 'TRUE') { ' (optional)' } else { '' }
    $msgs = @($t.SelectNodes('.//MESSAGE') | ForEach-Object { $_.TEXT; $_.InnerText } | Where-Object { $_ }) -join ' / '
    $line = "$result | $($t.NAME)$optional"
    if ($result -ne 'PASS' -and $msgs) { $line += ' | ' + $msgs.Substring(0, [Math]::Min(400, $msgs.Length)) }
    Log $line
}
Finish
