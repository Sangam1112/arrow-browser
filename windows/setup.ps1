# Bharat Browser for Windows: makes sure WSL 2 and Ubuntu are ready, then installs the
# browser's Linux package inside Ubuntu. Run (elevated) by the Setup program, which then
# creates the Windows shortcuts. Safe to run again: every step checks before it changes
# anything. Written for Windows PowerShell 5.1, the version built into Windows 10 and 11.
#
# Exit codes: 0 done, 1 failed (the reason is shown in this window), 3010 restart needed.
param(
    [Parameter(Mandatory = $true)][string]$Package,     # bharat-browser_X.Y.Z-1_all.deb
    [Parameter(Mandatory = $true)][string]$ResultFile   # receives the Ubuntu distribution's name
)

# Native commands report failure through exit codes, which are checked below. "Stop" would
# turn any harmless message wsl.exe prints on stderr into a fatal error in PowerShell 5.1.
$ErrorActionPreference = "Continue"
$env:WSL_UTF8 = "1"   # wsl.exe's own messages in UTF-8 instead of UTF-16
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "Bharat Browser Setup"

$MinBuild = 19044          # Windows 10 21H2: the oldest build WSLg (Linux windows on the desktop) supports
$NewDistro = "Ubuntu"
$Steps = 5

function Write-Step([int]$Number, [string]$Text) {
    Write-Host ""
    Write-Host "[$Number/$Steps] $Text" -ForegroundColor Cyan
}

function Stop-Setup([string]$Message, [int]$Code = 1) {
    Write-Host ""
    Write-Host $Message -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to close this window" | Out-Null
    exit $Code
}

# Runs wsl.exe with its output shown in this window and returns its exit code.
function Invoke-Wsl {
    & wsl.exe @args | Out-Host
    return $LASTEXITCODE
}

# Runs wsl.exe and returns its output as text (old WSL versions ignore WSL_UTF8 and
# answer in UTF-16, which shows up here as NUL characters between letters).
function Get-WslText {
    $text = (& wsl.exe @args 2>$null | Out-String) -replace "`0", ""
    return $text.Trim()
}

Write-Host "Bharat Browser Setup" -ForegroundColor Green
Write-Host "Bharat Browser is a Linux app. It runs on Windows through WSL 2, Microsoft's built-in Linux support."
Write-Host "Keep this window open until it says it is done."

# --- 1. Windows ----------------------------------------------------------------------
Write-Step 1 "Checking Windows"
$build = [Environment]::OSVersion.Version.Build
if ($build -lt $MinBuild) {
    Stop-Setup ("Bharat Browser needs Windows 11, or Windows 10 version 21H2 (build $MinBuild) or later. " +
                "This PC has build $build. Install Windows updates (Settings > Windows Update), then run Setup again.")
}
$computer = Get-CimInstance Win32_ComputerSystem
if (-not $computer.HypervisorPresent) {
    # VirtualizationFirmwareEnabled is only meaningful while no hypervisor is running yet.
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    if ($cpu.VirtualizationFirmwareEnabled -eq $false) {
        Stop-Setup ("Virtualization is turned off in this PC's firmware, and WSL 2 needs it. Restart into your " +
                    "BIOS/UEFI settings, turn on Intel VT-x or AMD-V (sometimes called SVM), then run Setup again.")
    }
}
Write-Host "Windows build ${build}: OK"

# --- 2. WSL --------------------------------------------------------------------------
Write-Step 2 "Installing or updating WSL"
# Only the up-to-date WSL (from Microsoft, not the old one built into Windows) knows --version.
if ((Invoke-Wsl --version) -ne 0) {
    Write-Host "Installing WSL..."
    if ((Invoke-Wsl --install --no-distribution) -ne 0) {
        $null = Invoke-Wsl --install   # older Windows builds don't know --no-distribution
    }
    if ((Invoke-Wsl --version) -ne 0) {
        Stop-Setup "WSL has been installed. Restart your PC, then run Bharat Browser Setup again to finish." 3010
    }
}
if ((Invoke-Wsl --update) -ne 0) {
    Write-Host "Couldn't update WSL (are you offline?). Continuing with the installed version." -ForegroundColor Yellow
}
$null = Invoke-Wsl --set-default-version 2

# --- 3. Ubuntu -----------------------------------------------------------------------
Write-Step 3 "Setting up Ubuntu"
$distros = @((Get-WslText --list --quiet) -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$distro = $distros | Where-Object { $_ -like "Ubuntu*" } | Select-Object -First 1
if ($distro) {
    Write-Host "Using your existing $distro."
} else {
    Write-Host "Installing Ubuntu (about 500 MB to download)."
    Write-Host "When Ubuntu asks, create a Linux username and password (they don't need to match Windows)."
    Write-Host "When you then see a prompt ending in `$, type exit and press Enter." -ForegroundColor Yellow
    $code = Invoke-Wsl --install -d $NewDistro
    if ($code -ne 0) {
        Stop-Setup ("Ubuntu could not be installed (error $code). If the message above mentions virtualization, " +
                    "turn on Intel VT-x or AMD-V in your BIOS/UEFI settings. If it asks for a restart, restart " +
                    "and run Setup again.")
    }
    $distro = $NewDistro
}

# A distribution created as WSL 1 can't show Linux windows on the desktop.
foreach ($line in ((Get-WslText --list --verbose) -split "`r?`n")) {
    if ($line -match ('^\*?\s*' + [regex]::Escape($distro) + '\s+\S+\s+(\d)\s*$') -and $Matches[1] -eq "1") {
        Write-Host "Converting $distro to WSL 2 (this can take a few minutes)..."
        if ((Invoke-Wsl --set-version $distro 2) -ne 0) {
            Stop-Setup "Couldn't convert $distro to WSL 2. Run 'wsl --set-version $distro 2' in PowerShell to see why."
        }
    }
}

# Starting it visibly first means that if Ubuntu still wants to create its user account,
# its questions appear in this window instead of being hidden.
$null = Invoke-Wsl -d $distro "--" true
if ((Get-WslText -d $distro "--" id -u) -in @("", "0")) {
    Stop-Setup ("$distro doesn't have a Linux user account yet. Open $distro from the Start menu, create a " +
                "username and password, close it, then run Bharat Browser Setup again.")
}

# --- 4. Browser ----------------------------------------------------------------------
Write-Step 4 "Updating Ubuntu and installing Bharat Browser (this can take several minutes)"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$code = Invoke-Wsl -d $distro -u root --cd $here "--" bash ./wsl-setup.sh system $Package
if ($code -ne 0) {
    Stop-Setup ("Installing Bharat Browser inside $distro failed (error $code); the reason is shown above. " +
                "Check your internet connection and run Setup again.")
}
# Save downloads to the Windows Downloads folder rather than one inside Linux.
$downloads = (New-Object -ComObject Shell.Application).NameSpace("shell:Downloads").Self.Path
$null = Invoke-Wsl -d $distro --cd $here "--" bash ./wsl-setup.sh user $downloads

# --- 5. Done -------------------------------------------------------------------------
Write-Step 5 "Finishing"
Set-Content -Path $ResultFile -Value $distro -Encoding Ascii
# Setup runs as administrator, which starts its own copy of WSL; stop it so the browser
# starts fresh from your normal (non-administrator) desktop shortcut.
$null = Invoke-Wsl --shutdown
Write-Host ""
Write-Host "Bharat Browser is installed. Setup will now add the desktop and Start menu shortcuts." -ForegroundColor Green
Start-Sleep -Seconds 3
exit 0
