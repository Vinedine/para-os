<#
.SYNOPSIS
    Move .md (and rendered deal-sheet .html) source files between their PARA
    homes and a flat collected folder.

.DESCRIPTION
    Two-state vault layout:
      - Spread:  each .md sits next to its .pdf sibling in projects/, areas/,
                 resources/, archive/, triage/.
      - Collect: every .md is moved into resources/mds/ with its vault-relative
                 path encoded into the filename (separator: '__').

    The vault's reader views it via Google Drive shortcuts into the PARA
    folders. In collected state, those folders contain only PDFs - no .md
    clutter. PDFs never move; only .md and deal-sheet .html files flip
    locations.

    Render PDFs in spread state via render.ps1. Typical edit cycle:
        .\flip.ps1 spread    # .md files back to their PARA paths
        # edit .md content
        .\render.ps1         # regenerate .pdf siblings
        .\flip.ps1 collect   # .md files back into resources/mds/

    The collected filename is the vault-relative path with '/' and '\' replaced
    by '__'. Example:
        projects\example-project\brief.md
        <-> resources\mds\projects__example-project__brief.md

    Both directions are idempotent. Filenames or folders that already contain
    '__' will round-trip incorrectly; none currently do.

.PARAMETER Mode
    collect | spread

.PARAMETER DryRun
    List planned moves without touching the filesystem.

.EXAMPLE
    .\flip.ps1 collect

.EXAMPLE
    .\flip.ps1 spread -DryRun

.NOTES
    Part of para-os (read-only iPad flavor). Identical copies of flip.ps1 live
    in each vault that uses this flavor. If you change one, propagate to the
    others.
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0, Mandatory)]
    [ValidateSet('collect', 'spread')]
    [string]$Mode,

    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$VaultRoot  = (Get-Location).Path
$SourcesDir = Join-Path $VaultRoot 'resources\mds'
$Separator  = '__'

# Top-level folders that hold .md files in spread state
$paraFolders = @('projects', 'areas', 'resources', 'archive', 'triage')

# Filenames never moved by collect (maintainer-tooling artifacts)
$denyFilenames = @('CLAUDE.md', 'AGENTS.md')

# Folder names that fence off .md files from being moved
$denyFolders = @('.claude', '.git', '.obsidian', '.vscode')

function Get-EncodedName([string]$relPath) {
    return ($relPath -replace '[\\/]', $Separator)
}

function Get-DecodedPath([string]$encodedName) {
    $parts = $encodedName -split [regex]::Escape($Separator)
    return Join-Path $VaultRoot ($parts -join '\')
}

function Test-InDenyFolder([string]$fullPath) {
    foreach ($folder in $denyFolders) {
        $pattern = "[\\/]$([regex]::Escape($folder))[\\/]"
        if ($fullPath -match $pattern) { return $true }
    }
    return $false
}

if ($Mode -eq 'collect') {
    if (-not (Test-Path $SourcesDir)) {
        if ($DryRun) {
            Write-Host "[dry] mkdir resources\mds"
        } else {
            New-Item -ItemType Directory -Path $SourcesDir | Out-Null
        }
    }

    $moved = 0
    $skipped = 0
    $collisions = 0

    foreach ($folder in $paraFolders) {
        $base = Join-Path $VaultRoot $folder
        if (-not (Test-Path $base)) { continue }

        # .md sources, plus deal-sheet .html - but only .html that already has a
        # rendered .pdf sibling, so raw saved-webpage .html (e.g. under sources/)
        # is left in place.
        $mds = Get-ChildItem -Path $base -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Extension -eq '.md' -or
                ($_.Extension -eq '.html' -and (Test-Path ([IO.Path]::ChangeExtension($_.FullName, '.pdf'))))
            }

        foreach ($md in $mds) {
            if ($denyFilenames -contains $md.Name) { $skipped++; continue }
            if (Test-InDenyFolder $md.FullName)    { $skipped++; continue }

            # Already inside resources\mds\ - leave it (collected state)
            if ($md.FullName.StartsWith($SourcesDir, [StringComparison]::OrdinalIgnoreCase)) {
                $skipped++
                continue
            }

            $rel     = $md.FullName.Substring($VaultRoot.Length).TrimStart('\', '/')
            $encoded = Get-EncodedName $rel
            $target  = Join-Path $SourcesDir $encoded

            if (Test-Path $target) {
                Write-Host "[collide] $rel -> resources\mds\$encoded (target exists)" -ForegroundColor Yellow
                $collisions++
                continue
            }

            if ($DryRun) {
                Write-Host "[dry] move $rel -> resources\mds\$encoded"
            } else {
                Write-Host "[move] $rel -> resources\mds\$encoded"
                Move-Item -Path $md.FullName -Destination $target
            }
            $moved++
        }
    }

    Write-Host ""
    Write-Host "[flip.ps1] collect: $moved moved, $skipped skipped (denylist or already collected), $collisions collision(s)"
    exit 0
}

if ($Mode -eq 'spread') {
    if (-not (Test-Path $SourcesDir)) {
        Write-Host "[flip.ps1] no resources\mds\ to spread from; nothing to do."
        exit 0
    }

    $moved = 0
    $collisions = 0

    # .md and deal-sheet .html both round-trip out of resources\mds.
    $mds = Get-ChildItem -Path $SourcesDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in '.md', '.html' }

    foreach ($md in $mds) {
        $target    = Get-DecodedPath $md.Name
        $targetDir = Split-Path $target -Parent
        $rel       = $target.Substring($VaultRoot.Length).TrimStart('\', '/')

        if (Test-Path $target) {
            Write-Host "[collide] $($md.Name) -> $rel (target exists)" -ForegroundColor Yellow
            $collisions++
            continue
        }

        if ($DryRun) {
            Write-Host "[dry] move resources\mds\$($md.Name) -> $rel"
        } else {
            if (-not (Test-Path $targetDir)) {
                New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            }
            Write-Host "[move] resources\mds\$($md.Name) -> $rel"
            Move-Item -Path $md.FullName -Destination $target
        }
        $moved++
    }

    Write-Host ""
    Write-Host "[flip.ps1] spread: $moved moved, $collisions collision(s)"
    exit 0
}
