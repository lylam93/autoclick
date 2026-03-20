param(
    [switch]$SkipUnitTests
)

$ErrorActionPreference = 'Stop'
$env:PYTHONPATH = 'src'

Write-Host 'Running syntax check...'
python -m compileall src
if ($LASTEXITCODE -ne 0) {
    throw 'Syntax check failed.'
}

if (-not $SkipUnitTests) {
    Write-Host 'Running unit tests...'
    python -m unittest discover -s tests -p "test_*.py" -v
    if ($LASTEXITCODE -ne 0) {
        throw 'Unit tests failed.'
    }
}

Write-Host 'Verification completed.'
