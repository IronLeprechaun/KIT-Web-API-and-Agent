#!/usr/bin/env pwsh

# KIT System Cleanup Script
# Automates common cleanup tasks for the development environment

param(
    [switch]$All,
    [switch]$Cache,
    [switch]$Logs,
    [switch]$NodeModules,
    [switch]$EmptyDirs,
    [switch]$Help
)

function Show-Help {
    Write-Host "KIT System Cleanup Script" -ForegroundColor Green
    Write-Host "=========================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Usage: .\cleanup.ps1 [OPTIONS]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Cyan
    Write-Host "  -All           Run all cleanup tasks"
    Write-Host "  -Cache         Clean Python cache files (__pycache__, *.pyc)"
    Write-Host "  -Logs          Remove log files"
    Write-Host "  -NodeModules   Remove and reinstall node_modules"
    Write-Host "  -EmptyDirs     Remove empty directories"
    Write-Host "  -Help          Show this help message"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Cyan
    Write-Host "  .\cleanup.ps1 -All"
    Write-Host "  .\cleanup.ps1 -Cache -Logs"
    Write-Host "  .\cleanup.ps1 -EmptyDirs"
}

function Remove-PythonCache {
    Write-Host "🧹 Cleaning Python cache files..." -ForegroundColor Yellow
    
    # Remove __pycache__ directories
    Get-ChildItem -Recurse -Directory -Name "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item $_ -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  Removed: $($_.FullName)" -ForegroundColor DarkGray
    }
    
    # Remove .pyc and .pyo files
    Get-ChildItem -Recurse -Include "*.pyc","*.pyo" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    
    Write-Host "✅ Python cache cleaned" -ForegroundColor Green
}

function Remove-LogFiles {
    Write-Host "🧹 Cleaning log files..." -ForegroundColor Yellow
    
    # Remove .log files
    Get-ChildItem -Recurse -Include "*.log" -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "  Removing: $($_.Name)" -ForegroundColor DarkGray
        Remove-Item $_ -Force -ErrorAction SilentlyContinue
    }
    
    # Clean backend logs directory
    if (Test-Path "backend/logs") {
        Get-ChildItem "backend/logs" -Include "*.log" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    }
    
    Write-Host "✅ Log files cleaned" -ForegroundColor Green
}

function Remove-EmptyDirectories {
    Write-Host "🧹 Cleaning empty directories..." -ForegroundColor Yellow
    
    # Find and remove empty directories (excluding critical ones)
    $emptyDirs = Get-ChildItem -Recurse -Directory | Where-Object {
        ($_.GetFileSystemInfos().Count -eq 0) -and 
        ($_.Name -notmatch "^(node_modules|\.venv|\.git|backend|frontend|scripts|tests)$")
    }
    
    $emptyDirs | ForEach-Object {
        Write-Host "  Removing empty directory: $($_.Name)" -ForegroundColor DarkGray
        Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    }
    
    if ($emptyDirs.Count -eq 0) {
        Write-Host "  No empty directories found" -ForegroundColor DarkGray
    }
    
    Write-Host "✅ Empty directories cleaned" -ForegroundColor Green
}

function Reset-NodeModules {
    Write-Host "🧹 Resetting node_modules..." -ForegroundColor Yellow
    
    # Frontend node_modules
    if (Test-Path "frontend/node_modules") {
        Write-Host "  Removing frontend/node_modules..." -ForegroundColor DarkGray
        Remove-Item "frontend/node_modules" -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    # Root node_modules (if any)
    if (Test-Path "node_modules") {
        Write-Host "  Removing root/node_modules..." -ForegroundColor DarkGray
        Remove-Item "node_modules" -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    # Reinstall frontend dependencies
    if (Test-Path "frontend/package.json") {
        Write-Host "  Reinstalling frontend dependencies..." -ForegroundColor DarkGray
        Set-Location "frontend"
        npm install --silent
        Set-Location ".."
    }
    
    Write-Host "✅ Node modules reset" -ForegroundColor Green
}

# Main execution
if ($Help) {
    Show-Help
    exit 0
}

Write-Host "🚀 Starting KIT System cleanup..." -ForegroundColor Cyan
Write-Host ""

if ($All -or $Cache) {
    Remove-PythonCache
}

if ($All -or $Logs) {
    Remove-LogFiles
}

if ($All -or $EmptyDirs) {
    Remove-EmptyDirectories
}

if ($All -or $NodeModules) {
    Reset-NodeModules
}

# Default behavior if no specific flags
if (-not ($All -or $Cache -or $Logs -or $NodeModules -or $EmptyDirs)) {
    Write-Host "No specific cleanup option selected. Running basic cleanup..." -ForegroundColor Yellow
    Remove-PythonCache
    Remove-LogFiles
}

Write-Host ""
Write-Host "✨ Cleanup completed!" -ForegroundColor Green
Write-Host "" 