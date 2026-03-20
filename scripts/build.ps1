param(
    [switch]$OneFile
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root

try {
    python -c "import PyInstaller" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'PyInstaller is not installed. Run: pip install .[build]'
    }

    $arguments = @(
        '-m', 'PyInstaller',
        '--noconfirm',
        '--clean',
        '--windowed',
        '--name', 'AdvancedBackgroundAutoClicker',
        '--paths', 'src'
    )

    if ($OneFile) {
        $arguments += '--onefile'
    }

    $arguments += 'src/autoclicker/__main__.py'

    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw 'PyInstaller build failed.'
    }

    Write-Host 'Build completed. Output is available in dist/AdvancedBackgroundAutoClicker.'
}
finally {
    Pop-Location
}
