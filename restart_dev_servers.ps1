# Script to stop and restart dev servers (FastAPI backend & Vite frontend)

# --- Configuration ---
$backendPort = 8000
$frontendPort = 5173 # Default Vite port

# Assuming the script is run from the workspace root 
# If you place this script elsewhere, you might need to adjust these paths
$workspaceRoot = $PSScriptRoot 
$backendDir = Join-Path -Path $workspaceRoot -ChildPath "backend"
$frontendDir = Join-Path -Path $workspaceRoot -ChildPath "frontend"
$backendVenvPython = Join-Path -Path $backendDir -ChildPath ".venv\\Scripts\\python.exe" # Path to python in backend venv

# Commands to start the servers
# For backend, we will now explicitly call the python interpreter from the venv
$backendStartCommand = $backendVenvPython
$backendStartArgs = @(
    "-m",
    "uvicorn",
    "api.app:app",
    "--reload",
    "--port",
    $backendPort.ToString()
)

# For frontend - use cmd.exe /c to ensure npm.cmd is handled correctly
$frontendStartCommand = "cmd.exe"
$frontendStartArgs = @(
    "/c",
    "npm",
    "run",
    "dev"
) 

# Script-level variables to store process objects
$script:backendProcessObject = $null
$script:frontendProcessObject = $null

# --- Trap for Ctrl+C to stop servers before exiting ---
trap [System.Management.Automation.PipelineStoppedException] {
    Write-Warning "GLOBAL TRAP: Ctrl+C (PipelineStoppedException) detected!" -ForegroundColor Red
    Write-Host "GLOBAL TRAP: Attempting to stop dev servers. Calling Stop-AllDevServers now..." -ForegroundColor DarkMagenta
    Stop-AllDevServers
    Write-Host "GLOBAL TRAP: Stop-AllDevServers call completed." -ForegroundColor DarkMagenta
    Write-Host "GLOBAL TRAP: Resetting console Ctrl+C behavior." -ForegroundColor DarkYellow
    if ($Host.Name -eq 'ConsoleHost') { # Only set if in actual console
        try { [Console]::TreatControlCAsInput = $false } catch {}
    }
    Write-Host "GLOBAL TRAP: Waiting 2 seconds before script terminates." -ForegroundColor DarkYellow
    Start-Sleep -Seconds 2
    Write-Host "GLOBAL TRAP: Exiting script now via BREAK." -ForegroundColor DarkCyan
    break # This will exit the current loop/script block
}

# --- Helper Function to Stop Processes by Port (More Robust) ---
function Stop-ProcessByPort {
    param (
        [int]$Port,
        [string]$ServerName # For logging
    )
    Write-Host "Verifying port $Port for $ServerName status..."
    $portFreed = $false
    $maxAttempts = 3 
    $attempt = 0

    # Initial check if port is already free
    if (!(Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue)) {
        Write-Host "Port $Port for $ServerName is already free." -ForegroundColor Green
        return $true
    }

    # If not free, then try to find and kill processes associated with the port
    # This part is mostly for cleanup if direct PID stop failed or wasn't available
    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        if ($connections) {
            $processIds = $connections.OwningProcess | Select-Object -Unique
            if ($processIds.Count -eq 0) {
                 Write-Host "Port $Port ($ServerName) in use, but no PIDs found via Get-NetTCPConnection." -ForegroundColor Yellow
            } else {
                foreach ($pid in $processIds) {
                    try {
                        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
                        Write-Host "Port $Port ($ServerName) used by PID $pid ($($proc.ProcessName)). Taskkilling..." 
                        taskkill /PID $pid /T /F | Out-Null
                    } catch { Write-Warning "Ex taskkilling PID $pid ($ServerName): $($_.Exception.Message)" }
                }
            }
        } else {
            # This case should have been caught by the initial check
            Write-Host "No connections found on port $Port for $ServerName during detailed check (should be free)."
            return $true 
        }
    } catch {
        Write-Warning "Ex Get-NetTCPConnection ($ServerName, Port $Port): $($_.Exception.Message)" 
        return $false # Cannot confirm, assume not freed
    }

    # Verification loop
    while ($attempt -lt $maxAttempts) {
        $attempt++
        $lingeringConnections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        if (!$lingeringConnections) {
            Write-Host "Port $Port ($ServerName) confirmed free after $attempt attempt(s)." -ForegroundColor Green
            $portFreed = $true
            break
        } else {
            Write-Host "Port $Port ($ServerName) still in use (attempt $attempt/$maxAttempts)."
            if ($attempt -lt $maxAttempts) { Start-Sleep -Seconds 1 } # Wait before next check if not the last attempt
        }
    }
    if (!$portFreed) {
        Write-Warning "Port $Port ($ServerName) NOT confirmed free."
    }
    return $portFreed
}

# --- Function to Force Stop Backend Uvicorn Processes ---
function Force-StopBackendUvicornProcesses {
    Write-Host "Force-Stopping Backend Uvicorn processes..." -ForegroundColor Magenta
    $killed = $false
    try {
        $escapedVenvPath = $backendVenvPython -replace '\\', '\\\\'
        $venvDirEscaped = (Join-Path -Path $backendDir -ChildPath ".venv") -replace '\\', '\\\\'
        
        $filters = @(
            "Name = 'python.exe' AND CommandLine LIKE '%uvicorn%' AND CommandLine LIKE '%api.app:app%'",
            "Name = 'python.exe' AND ExecutablePath = '$escapedVenvPath'",
            "Name = 'python.exe' AND ExecutablePath LIKE '$($venvDirEscaped)%'"
        )
        $procsToKill = @()
        foreach ($f in $filters) {
            $procsToKill += Get-CimInstance Win32_Process -Filter $f -EA SilentlyContinue
        }
        $uniqueProcs = $procsToKill | Sort-Object ProcessId | Get-Unique -AsString

        if ($uniqueProcs) {
            $uniqueProcs | FT ProcessId, Name, ExecutablePath, CommandLine -A -Wr | Out-String | Write-Host
            foreach ($p in $uniqueProcs) {
                Write-Host "Taskkilling PID $($p.ProcessId)"
                taskkill /PID $($p.ProcessId) /T /F | Out-Null
                $killed = $true
            }
        } else {
            Write-Host "No specific backend python.exe processes found by Force-Stop."
        }
    } catch {
        Write-Warning "Ex Force-StopBackend: $($_.Exception.Message)"
    }
    return $killed
}

function Stop-AllDevServers {
    Write-Host "----- Stopping All Dev Servers -----" -ForegroundColor Yellow
    if ($script:backendProcessObject -and !$script:backendProcessObject.HasExited) {
        Write-Host "Stopping stored backend PID $($script:backendProcessObject.Id) with taskkill /T /F..."
        taskkill /PID $script:backendProcessObject.Id /T /F | Out-Null
        $script:backendProcessObject = $null
    }
    if (!(Stop-ProcessByPort -Port $backendPort -ServerName "Backend")) {
        Force-StopBackendUvicornProcesses
        Start-Sleep -Seconds 1
        if (!(Stop-ProcessByPort -Port $backendPort -ServerName "Backend (after force)")) {
            Write-Error "FAILED to free backend port $backendPort."
        }
    }
    if ($script:frontendProcessObject -and !$script:frontendProcessObject.HasExited) {
        Write-Host "Stopping stored frontend PID $($script:frontendProcessObject.Id) with taskkill /T /F..."
        taskkill /PID $script:frontendProcessObject.Id /T /F | Out-Null
        $script:frontendProcessObject = $null
    }
    if (!(Stop-ProcessByPort -Port $frontendPort -ServerName "Frontend")) {
         Write-Warning "Failed to confirm frontend port $frontendPort free."
    }
    Write-Host "Server stop sequence complete." -ForegroundColor Yellow
}

function Start-AllDevServers {
    Write-Host "----- Starting All Dev Servers -----" -ForegroundColor Green
    # Backend
    if (Test-Path $backendStartCommand) {
        try {
            Write-Host "Starting Backend: $backendStartCommand $($backendStartArgs -join ' ')"
            $script:backendProcessObject = Start-Process $backendStartCommand $backendStartArgs -WorkingDirectory $backendDir -PassThru -EA Stop
            if ($script:backendProcessObject) { Write-Host "Backend process started (PID: $($script:backendProcessObject.Id))." }
        } catch {
            Write-Error "Ex starting backend: $($_.Exception.Message)"
            $script:backendProcessObject = $null
        }
    } else {
        Write-Error "Backend Python not found: $backendStartCommand"
    }
    Start-Sleep -Seconds 2
    # Frontend
    try {
        Write-Host "Starting Frontend: $frontendStartCommand $($frontendStartArgs -join ' ')"
        $script:frontendProcessObject = Start-Process $frontendStartCommand $frontendStartArgs -WorkingDirectory $frontendDir -PassThru -EA Stop
        if ($script:frontendProcessObject) { Write-Host "Frontend process started (PID: $($script:frontendProcessObject.Id))." }
    } catch {
        Write-Error "Ex starting frontend: $($_.Exception.Message)"
        $script:frontendProcessObject = $null
    }
    Write-Host "Server start sequence complete." -ForegroundColor Green
}

# --- Script Entry Point ---
Write-Host "Dev Server Management Script Initializing..." -ForegroundColor Cyan
Write-Host "Workspace: $workspaceRoot | Backend Python: $backendVenvPython" 
Write-Host "----------------------------------------------------"

Start-AllDevServers # Initial start without stopping

Write-Host "Initial server startup complete. Press Enter to restart, Ctrl+C to exit." -ForegroundColor Cyan
Write-Host "----------------------------------------------------"

# Change the default behavior of CTRL-C so that the script can intercept
if ($Host.Name -eq 'ConsoleHost') {
    try {
        [Console]::TreatControlCAsInput = $true
        # Sleep briefly and then flush the key buffer
        Start-Sleep -Milliseconds 100
        if ($Host.UI.RawUI.KeyAvailable) { # Only flush if keys are actually pending
            $Host.UI.RawUI.FlushInputBuffer()
        }
    } catch {
        Write-Warning "Failed to set [Console]::TreatControlCAsInput. Ctrl+C might not be caught gracefully."
    }
} else {
    Write-Warning "Not running in ConsoleHost. Advanced Ctrl+C handling might not work as expected."
}

while ($true) {
    Write-Host "Waiting for input: Enter to RESTART, Ctrl+C to EXIT..." -ForegroundColor DarkCyan
    
    # Wait for a key press
    while (-not $Host.UI.RawUI.KeyAvailable) {
        Start-Sleep -Milliseconds 200 # Check for key every 200ms
        # Future: Add a check here if background processes have unexpectedly exited to break loop
    }

    # A key is available, read it
    $keyInfo = $Host.UI.RawUI.ReadKey("NoEcho,AllowCtrlC,IncludeKeyDown")

    if ($keyInfo.Character -eq 3) { # ASCII 3 is Ctrl+C
        Write-Warning "Ctrl+C detected! Initiating server shutdown..."
        Stop-AllDevServers
        Write-Host "Servers shut down. Exiting script." -ForegroundColor Yellow
        break # Exit the while loop
    } elseif ($keyInfo.VirtualKeyCode -eq 13) { # VK_RETURN (Enter key)
        Write-Host "Enter pressed. Restarting servers..." -ForegroundColor Green
        Stop-AllDevServers
        Write-Host "Waiting a few seconds before restarting..."
        Start-Sleep -Seconds 3
        Start-AllDevServers
        Write-Host "Servers restarted. Waiting for input..." -ForegroundColor Cyan
    } else {
        # Optional: Handle other keys or ignore them
        # Write-Host "Key pressed: $($keyInfo.Character) (VK: $($keyInfo.VirtualKeyCode)). Ignoring." -ForegroundColor Gray
        # Flush any unexpected input if it wasn't Enter or Ctrl+C
        if ($Host.UI.RawUI.KeyAvailable) {
            $Host.UI.RawUI.FlushInputBuffer()
        }
    }
    Write-Host "----------------------------------------------------"
}

# Reset console behavior before script fully exits
if ($Host.Name -eq 'ConsoleHost') {
    Write-Host "Resetting console Ctrl+C behavior to default." -ForegroundColor Magenta
    try { [Console]::TreatControlCAsInput = $false } catch {}
}
Write-Host "Script finished."

# To run this script:
# 1. Save it as restart_dev_servers.ps1 in your project root (D:\_Programming\Python KIT System).
# 2. Open PowerShell.
# 3. Navigate to your project root: cd "D:\_Programming\Python KIT System"
# 4. If you haven't run scripts before, you might need to set the execution policy:
#    Set-ExecutionPolicy RemoteSigned -Scope Process 
#    (or -Scope CurrentUser if you prefer)
# 5. Run the script: .\restart_dev_servers.ps1 