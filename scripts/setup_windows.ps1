# Stage 3 - Host setup on Windows 11
# Run in elevated PowerShell if needed

Write-Host "Installing core host tools via winget..."
winget install -e --id Microsoft.VisualStudioCode
winget install -e --id Docker.DockerDesktop
winget install -e --id Git.Git

Write-Host "Installing WSL2 Ubuntu 22.04..."
wsl --install -d Ubuntu-22.04

Write-Host "Done. Reboot if prompted, then open Ubuntu and run scripts/setup_wsl.sh commands manually."
