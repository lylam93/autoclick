param(
    [switch]$BuildOnly
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$tempRoot = Join-Path $root '.pip-temp'
New-Item -ItemType Directory -Force $tempRoot | Out-Null

$previousTmp = $env:TMP
$previousTemp = $env:TEMP
$env:TMP = $tempRoot
$env:TEMP = $tempRoot

Push-Location $root
try {
    $arguments = @('-m', 'pip', 'install')
    if ($BuildOnly) {
        $arguments += '.[build]'
    }
    else {
        $arguments += '.[build,dev]'
    }

    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw 'Dependency installation failed.'
    }
}
finally {
    Pop-Location
    $env:TMP = $previousTmp
    $env:TEMP = $previousTemp
}
