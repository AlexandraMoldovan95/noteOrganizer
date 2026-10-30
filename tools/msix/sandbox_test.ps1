# Runs INSIDE Windows Sandbox, at logon (tools/msix/make_sandbox_test.py
# writes the .wsb that starts it). Everything it touches is the sandbox's
# own and vanishes when the sandbox closes; the only thing that leaves is
# C:\out\result.txt (a folder mapped from the host for it).
#
# The life of the Store package, played end to end, with the two packages
# build_msix.py --update made (the lower version, then the higher):
#   an older exe's notebook in AppData -> install -> first start
#   -> a note written -> update -> start -> uninstall -> reinstall -> start.
#   After each step: what the profile notebook holds, what the package's
#   private copy holds, and whether AppData's is intact.
#
# The first line refuses anywhere but the sandbox: on this computer it would
# trust a test certificate and write over AppData's NoteOrganizer notebook,
# where the built app kept the owner's until 2026-10-27 (tools/check_guest.py
# holds every script here to such a first line).

if ($env:USERNAME -ne 'WDAGUtilityAccount' -and $PSCommandPath -ne 'C:\pkg\sandbox_test.ps1') { Write-Output 'sandbox_test.ps1 runs only inside Windows Sandbox: double-click the .wsb that tools/msix/make_sandbox_test.py writes.'; exit 2 }

$ErrorActionPreference = 'Continue'
$log = 'C:\out\result.txt'
$utf8 = New-Object System.Text.UTF8Encoding $false
[IO.File]::WriteAllText($log, '', $utf8)
function Log($m) { [IO.File]::AppendAllText($log, ((Get-Date -Format 'HH:mm:ss') + '  ' + $m + "`r`n"), $utf8) }
function WriteJson($path, $text) { [IO.File]::WriteAllText($path, $text, $utf8) }

New-Item -ItemType Directory -Force C:\work | Out-Null
Log "== start: user $env:USERNAME, profile $env:USERPROFILE"

# 1. A test certificate, made and trusted only inside this sandbox.
$cert = New-SelfSignedCertificate -Type Custom -Subject 'CN=NoteOrganizerTest' -KeyUsage DigitalSignature `
    -FriendlyName 'NoteOrganizer test' -CertStoreLocation 'Cert:\CurrentUser\My' `
    -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3', '2.5.29.19={text}')
Export-Certificate -Cert $cert -FilePath C:\work\test.cer | Out-Null
Import-Certificate -FilePath C:\work\test.cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople | Out-Null
$versions = @(Get-ChildItem C:\pkg\NoteOrganizer_*.msix |
    ForEach-Object { $_.BaseName.Substring('NoteOrganizer_'.Length) } |
    Sort-Object { [version]$_ })
$first = $versions[0]
$later = $versions[-1]
foreach ($v in $versions) {
    Copy-Item "C:\pkg\NoteOrganizer_$v.msix" C:\work\
    $out = & C:\sdk\signtool.exe sign /fd SHA256 /sha1 $cert.Thumbprint "C:\work\NoteOrganizer_$v.msix" 2>&1
    Log "signed $v : exit $LASTEXITCODE $($out | Select-Object -Last 1)"
}

# 2. An older exe's notebook in AppData, where the exe kept it until 2026-10-27.
$old = Join-Path $env:APPDATA 'NoteOrganizer'
New-Item -ItemType Directory -Force $old | Out-Null
WriteJson (Join-Path $old 'notes_data.json') '[{"id":1,"uid":"sb-1","title":"From the old exe","body":"a","category":"General","created":"2026-10-01 09:00:00","updated":"2026-10-01 09:00:00"}]'
WriteJson (Join-Path $old 'settings.json') '{"app_version":"0.97.405","welcome_offered":true}'
$oldHash = (Get-FileHash (Join-Path $old 'notes_data.json')).Hash

$home2 = Join-Path $env:USERPROFILE 'Note Organizer'
$notesPath = Join-Path $home2 'notes_data.json'

function Titles {
    if (-not (Test-Path $notesPath)) { return '(no notebook)' }
    $parsed = Get-Content $notesPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $names = foreach ($x in $parsed) { $x.title }
    $same = if ($writtenHash) { " (file as written: $((Get-FileHash $notesPath).Hash -eq $writtenHash))" } else { '' }
    return ($names -join ' ; ') + $same
}
$writtenHash = $null

function Report($label) {
    Log "$label | profile notebook: $(Titles)"
    $pkg = Get-AppxPackage -Name NoteOrganizer.Test
    if ($pkg) {
        $priv = Join-Path $env:LOCALAPPDATA ("Packages\" + $pkg.PackageFamilyName + "\LocalCache")
        if (Test-Path $priv) {
            $files = @(Get-ChildItem $priv -Recurse -File | ForEach-Object { $_.FullName.Substring($priv.Length) })
            Log "$label | package's private copy: $($files.Count) file(s) $($files -join ', ')"
        } else { Log "$label | package's private copy: none" }
    } else { Log "$label | package: not installed" }
    $now = if (Test-Path (Join-Path $old 'notes_data.json')) { (Get-FileHash (Join-Path $old 'notes_data.json')).Hash } else { 'GONE' }
    Log "$label | AppData notebook unchanged: $($now -eq $oldHash)"
}

function RunApp($label) {
    $pkg = Get-AppxPackage -Name NoteOrganizer.Test
    Start-Process ("shell:AppsFolder\" + $pkg.PackageFamilyName + "!NoteOrganizer")
    Start-Sleep -Seconds 25
    $p = Get-Process NoteOrganizer -ErrorAction SilentlyContinue
    Log "$label | the app was running: $([bool]$p)"
    $p | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
}

function Install($v) {
    try { Add-AppxPackage -Path "C:\work\NoteOrganizer_$v.msix" -ErrorAction Stop; Log "installed $v" }
    catch { Log "INSTALL FAILED $v : $($_.Exception.Message)"; return }
    # The licenses About opens, where the app looks for them (sys._MEIPASS).
    $pkg = Get-AppxPackage -Name NoteOrganizer.Test
    $notices = Join-Path $pkg.InstallLocation '_internal\THIRD_PARTY_NOTICES.txt'
    Log "$v | the licenses ship inside the package: $(Test-Path $notices)"
}

Report 'before install'
Install $first
RunApp 'first start'
Report 'after the first start'

# 3. A note written after install, as a person would add one. Windows
# PowerShell hands a JSON array down the pipe as ONE object: wrapping it in
# @() nested the notes one list deeper, so each is enumerated into a list.
$parsed = Get-Content $notesPath -Raw -Encoding UTF8 | ConvertFrom-Json
$list = New-Object System.Collections.ArrayList
foreach ($x in $parsed) { [void]$list.Add($x) }
[void]$list.Add([pscustomobject]@{ id = 2; uid = 'sb-2'; title = 'Written after install'; body = 'b'; category = 'General'; created = '2026-10-27 09:00:00'; updated = '2026-10-27 09:00:00' })
WriteJson $notesPath (ConvertTo-Json -InputObject $list.ToArray() -Depth 8)
$writtenHash = (Get-FileHash $notesPath).Hash
Report 'a note written'

Install $later
RunApp 'start after the update'
Report "after the update to $later"

$pkg = Get-AppxPackage -Name NoteOrganizer.Test
Remove-AppxPackage -Package $pkg.PackageFullName
Log "uninstalled"
Start-Sleep -Seconds 3
Report 'after uninstall'

Install $later
RunApp 'start after reinstall'
Report 'after reinstall'
Log "== done. The sandbox can be closed."
Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show('The test has finished. You can close Windows Sandbox now.', 'Note Organizer test') | Out-Null
