<#
    Builds the flash-drive kit: the Arena plus the toolchains teams need,
    in one folder that runs from any Windows machine without installing
    anything or needing admin rights.

        IPD-Kit\
          Arena.exe          double-click this
          README.txt
          templates\         my_bot.py, MyBot.java
          Shell here.cmd     a terminal with the tools on PATH
          tools\python\      embeddable Python
          tools\jdk\         javac + java
          tools\mingw\       g++
          tools\licenses\

    Run this once on a Windows machine with internet, then copy the folder to
    as many drives as you like:

        pwsh -File make-kit.ps1 -Arena ..\arena\dist\Arena.exe

    Downloads are cached in .cache, and their SHA-256 hashes are recorded in
    hashes.json: the first run records, later runs verify. Check hashes.json
    into git so everyone builds the same kit.
#>
#Requires -Version 5.1
[CmdletBinding()]
param(
    # The Arena, built by .github/workflows/build-arena.yml or PyInstaller.
    [string]$Arena = "",
    [string]$Out = "IPD-Kit",
    [string]$PythonVersion = "3.12.7",
    [int]$JdkVersion = 21,
    # WinLibs GCC (UCRT). Newer builds: https://winlibs.com  (update the hash too)
    [string]$MingwUrl = "https://github.com/brechtsanders/winlibs_mingw/releases/download/14.2.0posix-19.1.1-12.0.0-ucrt-r2/winlibs-x86_64-posix-seh-gcc-14.2.0-mingw-w64ucrt-12.0.0-r2.zip",
    [switch]$TrimJdk,        # jlink a smaller JDK (still has javac): ~80 MB instead of ~300 MB
    [switch]$SkipMingw,      # leave C++ out
    [switch]$CheckOnly,      # just check the downloads are reachable, build nothing
    [ValidateSet("ipd", "rps")]
    [string]$Game = "ipd"    # rps builds the practice kit teams get beforehand
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$cache = Join-Path $root ".cache"
$hashFile = Join-Path $root "hashes.json"
New-Item -ItemType Directory -Force $cache | Out-Null

function Read-Hashes {
    if (Test-Path $hashFile) { return Get-Content $hashFile -Raw | ConvertFrom-Json }
    return [pscustomobject]@{}
}

function Save-Hash($name, $sha) {
    $h = Read-Hashes
    $h | Add-Member -NotePropertyName $name -NotePropertyValue $sha -Force
    $h | ConvertTo-Json | Set-Content $hashFile
}

function Get-Download($name, $url, $expected) {
    <# Cached download, verified against hashes.json (recorded on first run). #>
    $file = Join-Path $cache ("{0}{1}" -f $name, [IO.Path]::GetExtension(($url -split '\?')[0]))
    if (-not $file.EndsWith(".zip")) { $file = "$file.zip" }
    if ($CheckOnly) {
        $code = (Invoke-WebRequest -Uri $url -Method Head -MaximumRedirection 5).StatusCode
        Write-Host ("  {0,-8} {1}  {2}" -f $name, $code, $url)
        return $null
    }
    if (-not (Test-Path $file)) {
        Write-Host "  downloading $name …"
        Invoke-WebRequest -Uri $url -OutFile $file -MaximumRedirection 5
    }
    $sha = (Get-FileHash $file -Algorithm SHA256).Hash.ToLower()
    $known = if ($expected) { $expected.ToLower() } else { (Read-Hashes).$name }
    if ($known -and $known -ne $sha) {
        throw "$name hash mismatch`n  expected $known`n  got      $sha`nDelete $file and retry, or update hashes.json deliberately."
    }
    if (-not $known) {
        Write-Host "  recording hash for $name ($sha)"
        Save-Hash $name $sha
    }
    return $file
}

function Expand-Into($zip, $dest, $stripTop) {
    <# Expand, optionally lifting a single top-level folder out of the way. #>
    $tmp = Join-Path $cache ("x-" + [IO.Path]::GetFileNameWithoutExtension($zip))
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $src = $tmp
    if ($stripTop) {
        $top = Get-ChildItem $tmp
        if ($top.Count -eq 1 -and $top[0].PSIsContainer) { $src = $top[0].FullName }
    }
    New-Item -ItemType Directory -Force (Split-Path -Parent $dest) | Out-Null
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    Move-Item $src $dest
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
}

# ---------------------------------------------------------------- downloads

Write-Host "IPD kit"
$pyUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$api = "https://api.adoptium.net/v3/assets/latest/$JdkVersion/hotspot" +
       "?architecture=x64&image_type=jdk&os=windows&vendor=eclipse"
$jdkUrl = $null
$jdkSha = $null
if (-not $CheckOnly -or $true) {
    $asset = (Invoke-RestMethod -Uri $api)[0].binary.package
    $jdkUrl = $asset.link
    $jdkSha = $asset.checksum          # Adoptium publishes the checksum itself
}

$pyZip = Get-Download "python" $pyUrl $null
$jdkZip = Get-Download "jdk" $jdkUrl $jdkSha
$mingwZip = if ($SkipMingw) { $null } else { Get-Download "mingw" $MingwUrl $null }
if ($CheckOnly) { Write-Host "downloads reachable"; exit 0 }

# ----------------------------------------------------------------- assemble

$kit = Join-Path (Get-Location) $Out
$tools = Join-Path $kit "tools"
Write-Host "assembling $kit"
New-Item -ItemType Directory -Force $tools | Out-Null

Expand-Into $pyZip (Join-Path $tools "python") $false
Expand-Into $jdkZip (Join-Path $tools "jdk") $true
if ($mingwZip) { Expand-Into $mingwZip (Join-Path $tools "mingw") $true }

if ($TrimJdk) {
    Write-Host "  trimming the JDK with jlink …"
    $jdk = Join-Path $tools "jdk"
    $min = Join-Path $tools "jdk-min"
    if (Test-Path $min) { Remove-Item -Recurse -Force $min }
    & (Join-Path $jdk "bin\jlink.exe") --add-modules java.base,java.logging,java.xml,jdk.compiler,jdk.zipfs `
        --strip-debug --no-header-files --no-man-pages --compress=2 --output $min
    if ($LASTEXITCODE -ne 0) { throw "jlink failed" }
    Remove-Item -Recurse -Force $jdk
    Move-Item $min $jdk
}

# The Arena itself
if (-not $Arena) { $Arena = Join-Path $root "..\arena\dist\Arena.exe" }
if (Test-Path $Arena) {
    Copy-Item $Arena (Join-Path $kit "Arena.exe") -Force
} else {
    Write-Warning "Arena.exe not found at $Arena - copy it into $kit yourself (see the build workflow)"
}
$pack = if ($Game -eq "rps") { "..\starter\practice" } else { "..\starter" }
Copy-Item (Join-Path $root "$pack\README.md") (Join-Path $kit "README-protocol.md") -Force
$templates = Join-Path $kit "templates"
if (Test-Path $templates) { Remove-Item -Recurse -Force $templates }
Copy-Item -Recurse (Join-Path $root "$pack\templates") $templates
if ($Game -eq "rps") {
    # A game.txt beside the exe is what makes it the practice build.
    "rps" | Set-Content (Join-Path $kit "game.txt")
} elseif (Test-Path (Join-Path $kit "game.txt")) {
    Remove-Item (Join-Path $kit "game.txt")
}

# Licences, kept where people can find them
$licenses = Join-Path $tools "licenses"
New-Item -ItemType Directory -Force $licenses | Out-Null
foreach ($pair in @(@{from = "python\LICENSE.txt"; to = "python-LICENSE.txt" },
                    @{from = "jdk\legal"; to = "jdk-legal" },
                    @{from = "mingw\LICENSE.txt"; to = "mingw-LICENSE.txt" },
                    @{from = "mingw\licenses"; to = "mingw-licenses" })) {
    $src = Join-Path $tools $pair.from
    if (Test-Path $src) { Copy-Item -Recurse -Force $src (Join-Path $licenses $pair.to) }
}

@"
IPD Arena - everything you need, nothing to install
===================================================

1. Double-click Arena.exe.
2. Click "+ Add bot" and pick your bot's main file (templates\ has a starter
   in Python and Java; copy one and edit choose()).
3. Click "Check", then "Run tournament".

Python, Java and C++ all work straight from this folder: the Arena puts
tools\ on its own PATH. Nothing is installed and nothing on the machine is
changed. Windows may warn that the app is unsigned: More info -> Run anyway.

Prefer a terminal? "Shell here.cmd" opens one with python, javac and g++ ready.

The protocol your bot speaks is described in README-protocol.md.
Licences for the bundled tools are in tools\licenses\.
"@ | Set-Content (Join-Path $kit "README.txt")

@"
@echo off
rem A terminal with the kit's tools on PATH.
set "KIT=%~dp0"
set "JAVA_HOME=%KIT%tools\jdk"
set "PATH=%KIT%tools\python;%KIT%tools\jdk\bin;%KIT%tools\mingw\bin;%PATH%"
echo Python, javac and g++ are ready in this window.
cmd /k
"@ | Set-Content (Join-Path $kit "Shell here.cmd")

# ------------------------------------------------------------------ verify

Write-Host "checking the kit"
$py = Join-Path $tools "python\python.exe"
$javac = Join-Path $tools "jdk\bin\javac.exe"
$gpp = Join-Path $tools "mingw\bin\g++.exe"
& $py -V
& $javac -version
if (Test-Path $gpp) { & $gpp --version | Select-Object -First 1 }

# Compile and run the Java template with the bundled JDK, over the real protocol.
$work = Join-Path $cache "verify"
if (Test-Path $work) { Remove-Item -Recurse -Force $work }
New-Item -ItemType Directory -Force $work | Out-Null
Copy-Item (Join-Path $templates "java\MyBot.java") $work
Push-Location $work
& $javac MyBot.java
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "the bundled JDK could not compile the Java template" }
$moves = "RESET`nROUND - -`nROUND C D`nEND" | & (Join-Path $tools "jdk\bin\java.exe") -cp . MyBot
Pop-Location
if (($moves -join "") -notmatch "^[CD]+$") { throw "the Java template did not play: '$moves'" }
Write-Host "  java bot replied: $($moves -join ' ')"

$arenaExe = Join-Path $kit "Arena.exe"
if (Test-Path $arenaExe) {
    $report = Join-Path $cache "selftest.txt"
    $p = Start-Process -FilePath $arenaExe -ArgumentList '--selftest', $report -Wait -PassThru
    Get-Content $report
    if ($p.ExitCode -ne 0) { throw "Arena.exe self-test failed" }
}

$size = (Get-ChildItem $kit -Recurse -File | Measure-Object Length -Sum).Sum / 1GB
Write-Host ("kit ready: {0}  ({1:N2} GB)" -f $kit, $size)
Write-Host "copy that folder to a flash drive as it is."
