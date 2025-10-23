import os
import subprocess
import sys
from pathlib import Path

# Name of the shared Docker network
NETWORK_NAME = "wideresearch-network"

# Root folder to search for docker-compose.yml files
ROOT_DIR = Path(__file__).parent.resolve()


def create_network():
    """Create a shared Docker network if it doesn't exist"""
    result = subprocess.run(
        ["docker", "network", "ls", "--filter", f"name={NETWORK_NAME}", "-q"], capture_output=True, text=True
    )
    if not result.stdout.strip():
        print(f"[INFO] Creating Docker network: {NETWORK_NAME}")
        subprocess.run(["docker", "network", "create", NETWORK_NAME], check=True)
    else:
        print(f"[INFO] Docker network {NETWORK_NAME} already exists")


def find_compose_files():
    """Find all docker-compose.yml files in subfolders"""
    compose_files = list(ROOT_DIR.rglob("docker-compose.yml"))
    return sorted(compose_files)


def run_compose(file_path):
    """Run a docker-compose file"""
    print(f"[INFO] Bringing up {file_path}")
    subprocess.run(["docker", "compose", "-f", str(file_path), "up", "-d"], check=True)


def main():
    create_network()
    compose_files = find_compose_files()
    if not compose_files:
        print("[WARN] No docker-compose.yml files found!")
        sys.exit(1)

    for file_path in compose_files:
        run_compose(file_path)

    print("[INFO] All docker-compose projects are up!")


if __name__ == "__main__":
    main()
