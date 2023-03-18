#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import subprocess
from hashlib import md5
from pathlib import Path

import docker
import python_on_whales
import yaml
from pyroute2 import IPRoute


compose_name = 'output'
output_dir   = Path('./output')
compose_file = output_dir / 'docker-compose.yml'
backup_file  = output_dir / "docker-compose-backup.yml"
br_config    = output_dir / 'as153-br0'
client: docker.DockerClient = docker.from_env()


def md5_hash(x: str) -> str:
    return md5(x.encode('utf-8')).hexdigest()


def get_net_name(compose, subnet: str):
    for name, net in compose['networks'].items():
        for config in net['ipam']['config']:
            if type(config) == dict and config.get('subnet') == subnet:
                return f'{compose_name}_{name}'
    raise KeyError("No network using subnet " + subnet)


def get_br_name(docker_id):
    return f'br-{docker_id[:12]}'


def up(args):
    with open(compose_file, 'r') as f:
        compose = yaml.load(f, Loader=yaml.SafeLoader)

    # Edit the compose file to remove the router from as153
    if not os.path.exists(backup_file):
        shutil.copy(compose_file, backup_file)
        del compose['services']['rnode_153_br0']
        with open(compose_file, 'w') as f:
            yaml.dump(compose, f, indent=4)

    # Copy configuration for as153-br0
    if not br_config.exists():
        br_config_files = {
            md5_hash('/etc/scion/topology.json')           : 'topology.json',
            md5_hash('/etc/scion/br0.toml')                : 'br0.toml',
            md5_hash('/etc/scion/crypto/as/ISD1-AS153.pem'): 'crypto/as/ISD1-AS153.pem',
            md5_hash('/etc/scion/crypto/as/cp-as.key')     : 'crypto/as/cp-as.key',
            md5_hash('/etc/scion/crypto/as/cp-as.tmpl')    : 'crypto/as/cp-as.tmpl',
            md5_hash('/etc/scion/certs/ISD1-B1-S1.trc')    : 'certs/ISD1-B1-S1.trc',
            md5_hash('/etc/scion/keys/master0.key')        : 'keys/master0.key',
            md5_hash('/etc/scion/keys/master1.key')        : 'keys/master1.key',
        }
        src_dir = output_dir / 'rnode_153_br0'
        for src, dst in br_config_files.items():
            (br_config/dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src_dir/src, br_config/dst)
        with open(src_dir/md5_hash('/etc/scion/br0.toml'), 'r') as src:
            with open(br_config/'br0.toml', 'w') as dst:
                for line in src.readlines():
                    if not 'config_dir' in line:
                        dst.write(line)
                    else:
                        dst.write(f'config_dir = "{br_config}"')

    # Get loopback IP
    with open(br_config/'topology.json', 'r') as f:
        topo = json.load(f)
    loopback = topo['border_routers']['br0']['internal_addr'].split(':')[0]

    # Run emulator
    whales = python_on_whales.DockerClient(compose_files=[compose_file])
    whales.compose.up(detach=True)

    # Get Docker bridge networks
    net153_net0_name = get_net_name(compose, '10.153.0.0/24')
    xc_net_name = get_net_name(compose, '10.50.0.0/29')

    net153_net0 = client.networks.list(names=[net153_net0_name])[0]
    xc_net = client.networks.list(names=[xc_net_name])[0]

    # Create veths
    with IPRoute() as ipr:
        ipr.link('add', ifname='dummy0', kind='dummy')
        dummy0 = ipr.link_lookup(ifname='dummy0')[0]
        ipr.addr('add', index=dummy0, address=loopback, mask=32)
        ipr.link('set', index=dummy0, state='up')

        ipr.link('add', ifname='veth0', kind='veth', peer='veth1')
        veth0 = ipr.link_lookup(ifname='veth0')[0]
        veth1 = ipr.link_lookup(ifname='veth1')[0]
        br = ipr.link_lookup(ifname=get_br_name(net153_net0.id))[0]
        ipr.link('set', index=veth1, master=br)
        ipr.addr('add', index=veth1, address='10.153.0.2', mask=24)
        ipr.link('set', index=veth1, state='up')
        ipr.link('set', index=veth0, state='up')

        ipr.link('add', ifname='veth2', kind='veth', peer='veth3')
        veth2 = ipr.link_lookup(ifname='veth2')[0]
        veth3 = ipr.link_lookup(ifname='veth3')[0]
        br = ipr.link_lookup(ifname=get_br_name(xc_net.id))[0]
        ipr.link('set', index=veth3, master=br)
        ipr.addr('add', index=veth3, address='10.50.0.3', mask=29)
        ipr.link('set', index=veth3, state='up')
        ipr.link('set', index=veth2, state='up')

    # Run the router of as153 on the host
    subprocess.Popen(
        f"{args.border_router} --config {br_config/'br0.toml'} >> {br_config}/br0.log 2>&1",
        shell=True, start_new_session=True)


def down(args):
    subprocess.run(['pkill', '-fx', f"{args.border_router} --config {br_config/'br0.toml'}"])

    whales = python_on_whales.DockerClient(compose_files=[compose_file])
    whales.compose.down()

    with IPRoute() as ipr:
        ipr.link('del', index=ipr.link_lookup(ifname='dummy0')[0])
        ipr.link('del', index=ipr.link_lookup(ifname='veth0')[0])
        ipr.link('del', index=ipr.link_lookup(ifname='veth2')[0])


parser = argparse.ArgumentParser()
parser.add_argument('border_router', type=str, help='Path to SCION border router')
subparsers = parser.add_subparsers(required=True)
subparsers.add_parser('up').set_defaults(func=up)
subparsers.add_parser('down').set_defaults(func=down)
args = parser.parse_args()
args.func(args)
