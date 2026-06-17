# Stage 3 — Local Environment & Prerequisites

This stage prepares your local environment for the full robotics telemetry platform.

## 1) Recommended environment
- Host OS: Windows 11
- Editor: VS Code
- Linux runtime: WSL2 Ubuntu 22.04
- Containers: Docker Desktop with WSL integration
- Python: 3.10+

## 2) Minimum machine specs
- CPU: 6 logical cores (8 preferred)
- RAM: 16 GB (32 GB preferred)
- Disk: 60 GB free SSD

## 3) Install commands

### On Windows PowerShell
```powershell
winget install -e --id Microsoft.VisualStudioCode
winget install -e --id Docker.DockerDesktop
winget install -e --id Git.Git
wsl --install -d Ubuntu-22.04
```

### In WSL Ubuntu
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl gnupg2 lsb-release ca-certificates software-properties-common git build-essential python3-pip python3-venv unzip
```

## 4) Python virtual environment

```bash
cd ~/robot-telemetry-platform
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 5) Dependency list (pinned)
See [requirements.txt](../requirements.txt) for exact versions:
- kafka-python
- pydantic
- fastapi
- uvicorn
- prometheus-client
- pyspark
- delta-spark
- boto3
- psycopg2-binary
- duckdb
- pyarrow
- pandas

## 6) Verify setup

```bash
python -V
pip -V
docker --version
```

If these commands return versions without errors, Stage 3 is complete.
