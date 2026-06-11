<#
.SYNOPSIS
    Render every .md file in this vault to a sibling .pdf using a single
    persistent Chromium (Puppeteer + github-markdown-css).

.DESCRIPTION
    Walks the current folder recursively, finds .md files outside the denylist,
    and produces a .pdf sibling in the same folder. Skips files where the .pdf
    is already newer than the .md (unless -Force is passed).

    Output matches VS Code's Markdown preview: same engine (Chromium), same
    stylesheet family (github-markdown-css). The Node helper render.mjs does
    the actual rendering; this script handles file discovery, the denylist,
    and the mtime cache.

    Architecture: one Chromium boot per `.\render.ps1` invocation, not one per
    file. Batch runs (especially -Force) are ~10x faster than per-file CLIs.

    Run from the vault root after editing any .md content.

.PARAMETER VaultRoot
    Path to the vault. Defaults to the current directory.

.PARAMETER Force
    Re-render every .md regardless of modification times.

.EXAMPLE
    .\render.ps1
    Render any .md files newer than their .pdf sibling under the current folder.

.EXAMPLE
    .\render.ps1 -Force
    Re-render every .md.

.NOTES
    Part of para-os (read-only iPad flavor). This script lives in the root of
    each vault that uses this flavor. The copies are intended to be identical -
    if you change this file, propagate the change to the other vaults. See the
    vault CLAUDE.md for context.

    Version: 3.0 (2026-05-12) - Puppeteer with persistent browser via render.mjs.
                                Replaces v2.0's md-to-pdf (per-file cold start,
                                CDN-dependent stylesheets, prone to hangs).
#>

[CmdletBinding()]
param(
    [Parameter()]
    [string]$VaultRoot = (Get-Location).Path,

    [Parameter()]
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# Files never rendered (maintainer-tooling artifacts, not for the reader's view)
$denyFilenames = @('CLAUDE.md', 'AGENTS.md')

# Folders whose contents are never rendered
# 'mds' is the collected .md bucket used by flip.ps1; render only ever runs in spread state.
$denyFolders = @('.claude', '.git', '.obsidian', 'mds')

# Required npm packages (installed globally)
$requiredPackages = @('puppeteer', 'marked', 'github-markdown-css')

# --- Tool checks ---

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Host "Node.js not found on PATH." -ForegroundColor Red
    Write-Host "Install with: winget install OpenJS.NodeJS.LTS" -ForegroundColor Yellow
    exit 1
}

$globalRoot = (& npm root -g 2>$null) -join '' | ForEach-Object { $_.Trim() }
if (-not $globalRoot -or -not (Test-Path $globalRoot)) {
    Write-Host "Could not determine global npm modules folder (`npm root -g`)." -ForegroundColor Red
    exit 1
}

$missing = @()
foreach ($pkg in $requiredPackages) {
    if (-not (Test-Path (Join-Path $globalRoot $pkg))) {
        $missing += $pkg
    }
}
if ($missing.Count -gt 0) {
    Write-Host "Missing global npm packages: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "Install with: npm install -g $($missing -join ' ')" -ForegroundColor Yellow
    Write-Host "(Puppeteer also downloads a bundled Chromium - ~170 MB, one-time.)" -ForegroundColor Yellow
    exit 1
}

$renderMjs = Join-Path $VaultRoot 'render.mjs'
if (-not (Test-Path $renderMjs)) {
    Write-Host "render.mjs not found next to render.ps1 ($renderMjs)." -ForegroundColor Red
    exit 1
}

# --- Walk vault, build job list ---

Write-Host "[render.ps1] scanning $VaultRoot ..."
$mdFiles = Get-ChildItem -Path $VaultRoot -Recurse -Filter '*.md' -File

$jobs = @()
$skipped = 0
$denied = 0

foreach ($md in $mdFiles) {
    # Skip by filename
    if ($denyFilenames -contains $md.Name) {
        $denied++
        continue
    }

    # Skip if anywhere in the path is a denied folder
    $inDenyFolder = $false
    foreach ($folder in $denyFolders) {
        $pattern = "[\\/]$([regex]::Escape($folder))[\\/]"
        if ($md.FullName -match $pattern) {
            $inDenyFolder = $true
            break
        }
    }
    if ($inDenyFolder) {
        $denied++
        continue
    }

    $pdf = [IO.Path]::ChangeExtension($md.FullName, '.pdf')
    $relPath = $md.FullName.Substring($VaultRoot.Length).TrimStart('\', '/')

    # Skip if pdf is up to date
    if (-not $Force -and (Test-Path $pdf)) {
        $pdfFile = Get-Item $pdf
        if ($pdfFile.LastWriteTime -ge $md.LastWriteTime) {
            $skipped++
            continue
        }
    }

    $jobs += [pscustomobject]@{
        in   = $md.FullName
        out  = $pdf
        rel  = $relPath
        type = 'md'
    }
}

# --- Deal-sheet HTML: render <name>.html -> <name>.pdf (full styled documents,
# not markdown). Skip sources/, where raw saved webpages live. ---

$htmlFiles = Get-ChildItem -Path $VaultRoot -Recurse -Filter '*.html' -File
$htmlJobs = 0

foreach ($html in $htmlFiles) {
    $inDeny = $false
    foreach ($folder in ($denyFolders + @('sources'))) {
        $pattern = "[\\/]$([regex]::Escape($folder))[\\/]"
        if ($html.FullName -match $pattern) { $inDeny = $true; break }
    }
    if ($inDeny) { $denied++; continue }

    $pdf     = [IO.Path]::ChangeExtension($html.FullName, '.pdf')
    $relPath = $html.FullName.Substring($VaultRoot.Length).TrimStart('\', '/')

    if (-not $Force -and (Test-Path $pdf)) {
        if ((Get-Item $pdf).LastWriteTime -ge $html.LastWriteTime) {
            $skipped++
            continue
        }
    }

    $jobs += [pscustomobject]@{
        in   = $html.FullName
        out  = $pdf
        rel  = $relPath
        type = 'html'
    }
    $htmlJobs++
}

Write-Host "[render.ps1] found $($mdFiles.Count) .md + $($htmlFiles.Count) .html file(s); $($jobs.Count) to render ($htmlJobs html), $skipped up-to-date, $denied on denylist"

if ($jobs.Count -eq 0) {
    Write-Host "[render.ps1] nothing to render."
    exit 0
}

# --- Hand off to render.mjs ---

# Force array shape even if there's only one job (PowerShell would otherwise
# emit a bare object, which JSON.parse on the Node side would receive as non-array).
$json = ConvertTo-Json @($jobs) -Depth 4 -Compress

# NODE_PATH lets render.mjs resolve globally installed packages by name
$env:NODE_PATH = $globalRoot

Write-Host "[render.ps1] handing off to render.mjs ..."
Write-Host ""

# Pipe JSON via stdin; stream stdout/stderr live so the user sees progress
$json | & node $renderMjs
$exitCode = $LASTEXITCODE

Write-Host ""
if ($exitCode -ne 0) {
    Write-Host "[render.ps1] render.mjs exited with code $exitCode" -ForegroundColor Red
    exit $exitCode
}
Write-Host "[render.ps1] done."
