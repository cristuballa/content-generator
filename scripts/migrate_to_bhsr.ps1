# =============================================================================
# BHSR UNIFIED REPOSITORY MIGRATION SCRIPT
# Consolidates:
# - C:\Projects\BHRS-Youtube -> C:\Projects\BHSR\long_form
# - C:\Projects\Bible Hidden Secrets Revealed -> C:\Projects\BHSR
# - C:\Projects\Substack -> C:\Projects\BHSR\substack
# Creates Windows NTFS Directory Junctions (mklink /J) for 100% backward compatibility.
# =============================================================================

$ErrorActionPreference = "Stop"

$root = "C:\Projects"
$bhsr = "C:\Projects\BHSR"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  BHSR REPOSITORY RESTRUCTURING & CONSOLIDATION" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Create target directories in C:\Projects\BHSR
Write-Host "[1/5] Creating directory skeleton in $bhsr..." -ForegroundColor Yellow
$subdirs = @(
    "long_form",
    "reels",
    "stories",
    "shared_assets",
    "demucs_stems",
    "substack\assets",
    "substack\issues",
    "substack\digests",
    "scripts",
    "config",
    "reel_output"
)

foreach ($sub in $subdirs) {
    $targetPath = Join-Path $bhsr $sub
    if (-not (Test-Path $targetPath)) {
        New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
        Write-Host "  Created: $targetPath" -ForegroundColor DarkGray
    }
}

# 2. Migrate C:\Projects\BHRS-Youtube -> C:\Projects\BHSR\long_form
$bhrsDir = "C:\Projects\BHRS-Youtube"
if ((Test-Path $bhrsDir) -and -not (Get-Item $bhrsDir).Attributes.HasFlag([System.IO.FileAttributes]::ReparsePoint)) {
    Write-Host "[2/5] Migrating $bhrsDir -> $bhsr\long_form..." -ForegroundColor Yellow
    Get-ChildItem -Path $bhrsDir | ForEach-Object {
        $dest = Join-Path "$bhsr\long_form" $_.Name
        if (-not (Test-Path $dest)) {
            Move-Item -Path $_.FullName -Destination $dest -Force
        }
    }
    Remove-Item -Path $bhrsDir -Force -Recurse
    # Create Junction
    cmd.exe /c mklink /J "$bhrsDir" "$bhsr\long_form"
    Write-Host "  Created Junction: $bhrsDir -> $bhsr\long_form" -ForegroundColor Green
} else {
    Write-Host "[2/5] $bhrsDir already migrated or is a Junction. Skipping." -ForegroundColor DarkGray
}

# 3. Migrate C:\Projects\Bible Hidden Secrets Revealed -> C:\Projects\BHSR
$bhsrOld = "C:\Projects\Bible Hidden Secrets Revealed"
if ((Test-Path $bhsrOld) -and -not (Get-Item $bhsrOld).Attributes.HasFlag([System.IO.FileAttributes]::ReparsePoint)) {
    Write-Host "[3/5] Migrating $bhsrOld -> $bhsr..." -ForegroundColor Yellow
    
    # Specific known folders
    $moveFolders = @("reels", "stories", "shared_assets", "demucs_stems", "reel_output", ".venv_vibevoice", "scratch")
    foreach ($mf in $moveFolders) {
        $srcMf = Join-Path $bhsrOld $mf
        if (Test-Path $srcMf) {
            $destMf = Join-Path $bhsr $mf
            if (-not (Test-Path $destMf)) {
                Move-Item -Path $srcMf -Destination $destMf -Force
            } else {
                # Merge contents
                Get-ChildItem -Path $srcMf | ForEach-Object {
                    $itemDest = Join-Path $destMf $_.Name
                    if (-not (Test-Path $itemDest)) {
                        Move-Item -Path $_.FullName -Destination $itemDest -Force
                    }
                }
                Remove-Item -Path $srcMf -Force -Recurse -ErrorAction SilentlyContinue
            }
            Write-Host "  Moved folder: $mf" -ForegroundColor DarkGray
        }
    }

    # Move remaining files from root
    Get-ChildItem -Path $bhsrOld -File | ForEach-Object {
        $fileDest = Join-Path $bhsr $_.Name
        if (-not (Test-Path $fileDest)) {
            Move-Item -Path $_.FullName -Destination $fileDest -Force
        }
    }

    Remove-Item -Path $bhsrOld -Force -Recurse -ErrorAction SilentlyContinue
    # Create Junction
    cmd.exe /c mklink /J "$bhsrOld" "$bhsr"
    Write-Host "  Created Junction: $bhsrOld -> $bhsr" -ForegroundColor Green
} else {
    Write-Host "[3/5] $bhsrOld already migrated or is a Junction. Skipping." -ForegroundColor DarkGray
}

# 4. Migrate C:\Projects\Substack -> C:\Projects\BHSR\substack
$subOld = "C:\Projects\Substack"
if ((Test-Path $subOld) -and -not (Get-Item $subOld).Attributes.HasFlag([System.IO.FileAttributes]::ReparsePoint)) {
    Write-Host "[4/5] Migrating $subOld -> $bhsr\substack\assets..." -ForegroundColor Yellow
    Get-ChildItem -Path $subOld | ForEach-Object {
        $subDest = Join-Path "$bhsr\substack\assets" $_.Name
        if (-not (Test-Path $subDest)) {
            Move-Item -Path $_.FullName -Destination $subDest -Force
        }
    }
    Remove-Item -Path $subOld -Force -Recurse
    cmd.exe /c mklink /J "$subOld" "$bhsr\substack"
    Write-Host "  Created Junction: $subOld -> $bhsr\substack" -ForegroundColor Green
} else {
    Write-Host "[4/5] $subOld already migrated or is a Junction. Skipping." -ForegroundColor DarkGray
}

# 5. Archive Bible-Mysteries metadata/scripts into BHSR config
$bmOld = "C:\Projects\Bible-Mysteries"
if (Test-Path $bmOld) {
    Write-Host "[5/5] Backing up Bible-Mysteries catalogs into $bhsr\config\bible_mysteries..." -ForegroundColor Yellow
    $bmConfigDest = Join-Path "$bhsr\config" "bible_mysteries"
    if (-not (Test-Path $bmConfigDest)) {
        New-Item -ItemType Directory -Path $bmConfigDest -Force | Out-Null
    }
    Get-ChildItem -Path $bmOld -Filter "*.json" | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination (Join-Path $bmConfigDest $_.Name) -Force
    }
    Get-ChildItem -Path $bmOld -Filter "*.py" | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination (Join-Path "$bhsr\scripts" $_.Name) -Force
    }
    Write-Host "  Copied Bible-Mysteries catalogs and scripts." -ForegroundColor DarkGray
}

Write-Host "============================================================" -ForegroundColor Green
Write-Host "  BHSR REPOSITORY MIGRATION COMPLETED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
