# Copy the reel2rules Claude Code skills into your user skills folder (or a project's .claude\skills with -Project).
param([string]$Project = "")
$src = Join-Path $PSScriptRoot "..\skills"
$dst = if ($Project) { Join-Path $Project ".claude\skills" } else { Join-Path $HOME ".claude\skills" }
New-Item -ItemType Directory -Force $dst | Out-Null
foreach ($s in "strategy-extract", "strategy-test") {
    if (Test-Path (Join-Path $dst $s)) { Write-Host "skip $s (already exists in $dst - remove it first to update)"; continue }
    Copy-Item -Recurse (Join-Path $src $s) (Join-Path $dst $s)
    Write-Host "installed $s -> $dst"
}
