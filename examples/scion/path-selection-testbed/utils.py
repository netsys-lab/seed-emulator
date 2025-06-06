import sqlite3
import subprocess
import os
import time
import sys
import yaml

def init_db(db_path, schema_path):
    if not os.path.exists(db_path):
        with sqlite3.connect(db_path) as conn:
            with open(schema_path, 'r') as f:
                sql = f.read()
            conn.executescript(sql)
        print(f"Database created at {db_path}")
    else:
        print(f"Database already exists at {db_path}")


def run_command(cmd, timeout=300):
    """Run a shell command with timeout and basic error handling."""
    try:
        subprocess.run(cmd, check=True, timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        print(f"Command timed out: {' '.join(cmd)}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}")
        return False

def svn_checkout(repo_url, dest_dir, max_retries=3, delay=5):
    if os.path.exists(dest_dir):
        print(f"[svn] Directory '{dest_dir}' already exists. Skipping checkout.")
        return True

    for attempt in range(1, max_retries + 1):
        print(f"[svn] Attempt {attempt}: Checking out {repo_url} into {dest_dir}")
        if run_command(["svn", "checkout", repo_url, dest_dir]):
            print("[svn] Checkout successful.")
            return True
        else:
            print("[svn] Checkout failed.")
            if os.path.exists(dest_dir):
                print("[svn] Attempting cleanup...")
                run_command(["svn", "cleanup", dest_dir])
        if attempt < max_retries:
            print(f"[svn] Retrying in {delay} seconds...")
            time.sleep(delay)
    print("[svn] Max retries reached. Exiting.")
    sys.exit(1)

def git_clone(repo_url, dest_dir):
    if os.path.exists(dest_dir):
        print(f"[git] Directory '{dest_dir}' already exists. Skipping clone.")
        return True

    print(f"[git] Cloning {repo_url} into {dest_dir}")
    if run_command(["git", "clone", repo_url, dest_dir]):
        print("[git] Clone successful.")
        return True
    else:
        print("[git] Clone failed.")
        sys.exit(1)

def get_subnet_24(ip_address: str) -> str:
    return '.'.join(ip_address.split('.')[:3]) + '.0/24'



def add_macvlan_docker_compose(container_name, network_name, gateway_ip, ip_address, parent_dev_name):
    with open('output/docker-compose.yml', 'r') as f:
        docker_compose = yaml.safe_load(f)  

        if container_name not in docker_compose['services']:
            print(f"Container {container_name} not found in docker-compose.yml")
            return
        
        network = {
            'driver': 'macvlan',
            'driver_opts': {
                'parent': parent_dev_name
            },
            'ipam': {
                'config': [
                    {
                        'subnet': get_subnet_24(gateway_ip),
                        'gateway': gateway_ip
                    }
                ]
            }
        }
        if 'networks' not in docker_compose:
            docker_compose['networks'] = {}
        docker_compose['networks'][network_name] = network

        if 'networks' not in docker_compose['services'][container_name]:
            docker_compose['services'][container_name]['networks'] = {}
        if network_name not in docker_compose['services'][container_name]['networks']:
            docker_compose['services'][container_name]['networks'][network_name] = {}
        docker_compose['services'][container_name]['networks'][network_name]['ipv4_address'] = ip_address

    with open('output/docker-compose.yml', 'w') as f:
        yaml.dump(docker_compose, f)