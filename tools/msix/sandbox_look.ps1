# Runs INSIDE Windows Sandbox, at logon (tools/msix/make_sandbox_test.py
# writes the .wsb that starts it, with 2 GB of memory). The package to ship
# on a clean Windows with little memory, started once in each of its eight
# themes on a notebook of 40 notes. Each time: how soon its window shows,
# whether the window lies inside its monitor's work area (above the
# taskbar), a photo of the window inside the sandbox, the app's memory and
# the sandbox's, whether it closes as the X closes it, whether the theme is
# kept, and no crash log. Only C:\out leaves the sandbox: out\look\.
#
# The first line refuses anywhere but the sandbox, as sandbox_test.ps1's
# does: on this computer the app would open the owner's own notebook, which
# this script writes over.

if ($env:USERNAME -ne 'WDAGUtilityAccount' -or $PSCommandPath -ne 'C:\pkg\sandbox_look.ps1') { Write-Output 'sandbox_look.ps1 runs only inside Windows Sandbox: double-click the .wsb that tools/msix/make_sandbox_test.py writes.'; exit 2 }

$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force C:\out\look | Out-Null
$log = 'C:\out\look\look.txt'
$utf8 = New-Object System.Text.UTF8Encoding $false
[IO.File]::WriteAllText($log, '', $utf8)
function Log($m) { [IO.File]::AppendAllText($log, ((Get-Date -Format 'HH:mm:ss') + '  ' + $m + "`r`n"), $utf8) }

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName PresentationFramework
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class W {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern int GetDpiForSystem();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L; public int T; public int R; public int B; }
  [StructLayout(LayoutKind.Sequential)] public struct MONITORINFO { public int Size; public RECT Monitor; public RECT Work; public uint Flags; }
  [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int a, out RECT r, int s);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern IntPtr MonitorFromWindow(IntPtr h, uint flags);
  [DllImport("user32.dll")] public static extern bool GetMonitorInfo(IntPtr m, ref MONITORINFO i);
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool PostMessageW(IntPtr h, uint m, IntPtr w, IntPtr l);
  // The app's largest visible window: its main one. Process.MainWindowHandle
  // once named a tooltip that opened under the resting pointer.
  public static IntPtr Largest(int pid) {
    IntPtr best = IntPtr.Zero; long most = 0;
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      uint p; GetWindowThreadProcessId(h, out p);
      if (p == (uint)pid && IsWindowVisible(h)) {
        RECT r; DwmGetWindowAttribute(h, 9, out r, 16);
        long a = (long)(r.R - r.L) * (r.B - r.T);
        if (a > most) { most = a; best = h; }
      }
      return true;
    }, IntPtr.Zero);
    return best;
  }
  // Whether the window's visible frame lies inside its monitor's work area.
  public static bool Inside(IntPtr h) {
    RECT r; DwmGetWindowAttribute(h, 9, out r, 16);
    MONITORINFO i = new MONITORINFO(); i.Size = Marshal.SizeOf(typeof(MONITORINFO));
    GetMonitorInfo(MonitorFromWindow(h, 2), ref i);
    return r.L >= i.Work.L && r.T >= i.Work.T && r.R <= i.Work.R && r.B <= i.Work.B;
  }
}
"@
# Real pixels, so the window's frame, the work area and the photo agree.
[void][W]::SetProcessDPIAware()

$cs = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem
$dpi = [W]::GetDpiForSystem()
Log ("== start: memory {0} MB, free {1} MB, screen {2} dpi ({3}%), Windows {4}" -f [int]($cs.TotalPhysicalMemory / 1MB), [int]($os.FreePhysicalMemory / 1KB), $dpi, [int]($dpi * 100 / 96), $os.Version)

# The packages' own identity, read from the manifest: the test one until
# Partner Center reserves the Store's, then that one (build_msix.py --name and
# --publisher), so the package that ships is the one signed and proved. The
# same lines are in each sandbox script: each runs alone in its sandbox.
Add-Type -AssemblyName System.IO.Compression.FileSystem
function PackageIdentity($path) {
    $zip = [IO.Compression.ZipFile]::OpenRead($path)
    try {
        $reader = New-Object IO.StreamReader($zip.GetEntry('AppxManifest.xml').Open())
        try { $manifest = [xml]$reader.ReadToEnd() } finally { $reader.Dispose() }
    } finally { $zip.Dispose() }
    $element = $manifest.DocumentElement.Item('Identity')
    @{ Name = $element.GetAttribute('Name'); Publisher = $element.GetAttribute('Publisher') }
}
$identity = PackageIdentity (@(Get-ChildItem C:\pkg\NoteOrganizer_*.msix)[0].FullName)
Log "identity: $($identity.Name), $($identity.Publisher)"

# The package to ship: the lower of the pair build_msix.py --update made.
New-Item -ItemType Directory -Force C:\work | Out-Null
$cert = New-SelfSignedCertificate -Type Custom -Subject $identity.Publisher -KeyUsage DigitalSignature `
    -FriendlyName 'NoteOrganizer test' -CertStoreLocation 'Cert:\CurrentUser\My' `
    -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3', '2.5.29.19={text}')
Export-Certificate -Cert $cert -FilePath C:\work\test.cer | Out-Null
Import-Certificate -FilePath C:\work\test.cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople | Out-Null
$v = @(Get-ChildItem C:\pkg\NoteOrganizer_*.msix |
    ForEach-Object { $_.BaseName.Substring('NoteOrganizer_'.Length) } |
    Sort-Object { [version]$_ })[0]
Copy-Item "C:\pkg\NoteOrganizer_$v.msix" C:\work\
$out = & C:\sdk\signtool.exe sign /fd SHA256 /sha1 $cert.Thumbprint "C:\work\NoteOrganizer_$v.msix" 2>&1
Log "signed $v : exit $LASTEXITCODE"
try { Add-AppxPackage -Path "C:\work\NoteOrganizer_$v.msix" -ErrorAction Stop; Log "installed $v" }
catch { Log "INSTALL FAILED $v : $($_.Exception.Message)"; Log '== done.'; exit 1 }
$pkg = Get-AppxPackage -Name $identity.Name

# The notebook, where the packaged app keeps it: the profile's Note Organizer.
$book = Join-Path $env:USERPROFILE 'Note Organizer'
New-Item -ItemType Directory -Force $book | Out-Null
$notesPath = Join-Path $book 'notes_data.json'
$settingsPath = Join-Path $book 'settings.json'
Copy-Item C:\pkg\look_notes.json $notesPath
[IO.File]::WriteAllText($settingsPath, '{"welcome_offered": true}', $utf8)
Log "notebook: $((Get-Content $notesPath -Raw -Encoding UTF8 | ConvertFrom-Json).Count) notes"

$themes = 'dark', 'dark_ocean', 'dark_forest', 'dark_slate', 'light', 'light_sky', 'light_mint', 'light_warm'
foreach ($t in $themes) {
    $s = Get-Content $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $s | Add-Member -NotePropertyName theme -NotePropertyValue $t -Force
    [IO.File]::WriteAllText($settingsPath, (ConvertTo-Json -InputObject $s -Depth 8), $utf8)

    $started = Get-Date
    Start-Process ("shell:AppsFolder\" + $pkg.PackageFamilyName + "!NoteOrganizer")
    $p = $null; $hwnd = [IntPtr]::Zero
    while (((Get-Date) - $started).TotalSeconds -lt 60) {
        $p = Get-Process NoteOrganizer -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($p) { $hwnd = [W]::Largest($p.Id) }
        if ($hwnd -ne [IntPtr]::Zero) { break }
        Start-Sleep -Milliseconds 500
    }
    if ($hwnd -eq [IntPtr]::Zero) {
        Log "$t | NO WINDOW within 60 s"
        Get-Process NoteOrganizer -ErrorAction SilentlyContinue | Stop-Process -Force
        continue
    }
    $shown = [int]((Get-Date) - $started).TotalSeconds
    Start-Sleep -Seconds 8
    $hwnd = [W]::Largest($p.Id)
    [void][W]::SetForegroundWindow($hwnd)
    Start-Sleep -Milliseconds 800
    $r = New-Object 'W+RECT'
    [void][W]::DwmGetWindowAttribute($hwnd, 9, [ref]$r, 16)
    $w = $r.R - $r.L; $h = $r.B - $r.T
    if ($w -gt 0 -and $h -gt 0) {
        $bmp = New-Object System.Drawing.Bitmap $w, $h
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
        $bmp.Save("C:\out\look\look-$t.png", [System.Drawing.Imaging.ImageFormat]::Png)
        $g.Dispose(); $bmp.Dispose()
    }
    $free = [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1KB)
    $p.Refresh()
    Log ("$t | window after $shown s: ${w}x$h, inside the work area: $([W]::Inside($hwnd)) | app memory {0} MB (private {1} MB), sandbox free $free MB" -f [int]($p.WorkingSet64 / 1MB), [int]($p.PrivateMemorySize64 / 1MB))
    [void][W]::PostMessageW($hwnd, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)   # WM_CLOSE, as the X does
    $closed = $p.WaitForExit(20000)
    if (-not $closed) { $p | Stop-Process -Force }
    Start-Sleep -Seconds 1
    $kept = (Get-Content $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json).theme
    $now = (Get-Content $notesPath -Raw -Encoding UTF8 | ConvertFrom-Json).Count
    Log "$t | closed when asked: $closed | theme kept: $($kept -eq $t) | notes: $now | crash log: $(Test-Path (Join-Path $book 'crash_log.txt'))"
    Start-Sleep -Seconds 2
}
Log "== done. The sandbox can be closed."
[System.Windows.MessageBox]::Show('The test has finished. You can close Windows Sandbox now.', 'Note Organizer test') | Out-Null
