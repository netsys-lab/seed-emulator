#!/usr/bin/env python3

import re
import time
import argparse
import json
import signal
import pathlib

import docker
import python_on_whales

from seedemu.compiler import Docker, Graphviz
from seedemu.core import Emulator, Binding, Filter
from seedemu.layers import (
    ScionBase, ScionRouting, ScionIsd, Scion,
    Ospf, Ibgp, Ebgp, PeerRelationship
)
from seedemu.layers.Scion import LinkType as ScLinkType
from seedemu.services import ScionKuboService

#

emu = Emulator()
base = ScionBase()
routing = ScionRouting()
ospf = Ospf()
scion_isd = ScionIsd()
scion = Scion()
ibgp = Ibgp()
ebgp = Ebgp()
scionkubo = ScionKuboService()

# Parse CLI args
parser = argparse.ArgumentParser(__package__)
parser.add_argument('--path-strategy', type=int, required=True)
parser.add_argument('--content-size', type=int, required=True)
parser.add_argument('--num-nodes', type=int, required=True)
parser.add_argument('--output-file', type=pathlib.Path, required=True)
args = parser.parse_args()

# Open file to write results
file = open(args.output_file, mode='w', encoding='utf-8')
file.write(
    'path_strategy={}, content_size={}, num_nodes={}\n'.format(
        args.path_strategy, args.content_size, args.num_nodes)
)

#

base.createIsolationDomain(1)

#

base.createInternetExchange(150)
base.createInternetExchange(151)

#

as101 = base.createAutonomousSystem(101)
scion_isd.addIsdAs(1, 101, is_core=True)
as101.createNetwork('net0')
cs1 = as101.createControlService('cs1').joinNetwork('net0')
router = as101.createRouter('br0')
router.joinNetwork('net0').joinNetwork('ix150')
router2 = as101.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router.appendStartCommand('tcset ix150 --delay=20ms --rate 10000Kbps --overwrite')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

as102 = base.createAutonomousSystem(102)
scion_isd.addIsdAs(1, 102, is_core=True)
as102.createNetwork('net0')
cs1 = as102.createControlService('cs1').joinNetwork('net0')
router = as102.createRouter('br0')
router.joinNetwork('net0').joinNetwork('ix150')
router2 = as102.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router.appendStartCommand('tcset ix150 --delay=20ms --rate 10000Kbps --overwrite')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

as103 = base.createAutonomousSystem(103)
scion_isd.addIsdAs(1, 103, is_core=True)
as103.createNetwork('net0')
cs1 = as103.createControlService('cs1').joinNetwork('net0')
router = as103.createRouter('br0')
router.joinNetwork('net0').joinNetwork('ix150')
router2 = as103.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router.appendStartCommand('tcset ix150 --delay=20ms --rate 10000Kbps --overwrite')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

as104 = base.createAutonomousSystem(104)
scion_isd.addIsdAs(1, 104, is_core=True)
as104.createNetwork('net0')
cs1 = as104.createControlService('cs1').joinNetwork('net0')
router = as104.createRouter('br0')
router.joinNetwork('net0').joinNetwork('ix150')
router2 = as104.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router.appendStartCommand('tcset ix150 --delay=20ms --rate 10000Kbps --overwrite')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

as105 = base.createAutonomousSystem(105)
scion_isd.addIsdAs(1, 105, is_core=True)
as105.createNetwork('net0')
cs1 = as105.createControlService('cs1').joinNetwork('net0')
router = as105.createRouter('br0')
router.joinNetwork('net0').joinNetwork('ix150')
router2 = as105.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router.appendStartCommand('tcset ix150 --delay=20ms --rate 10000Kbps --overwrite')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

#

scion.addIxLink(150, (1, 101), (1, 102), ScLinkType.Core)
scion.addIxLink(150, (1, 101), (1, 103), ScLinkType.Core)
scion.addIxLink(150, (1, 101), (1, 104), ScLinkType.Core)
scion.addIxLink(150, (1, 101), (1, 105), ScLinkType.Core)
scion.addIxLink(150, (1, 102), (1, 103), ScLinkType.Core)
scion.addIxLink(150, (1, 102), (1, 104), ScLinkType.Core)
scion.addIxLink(150, (1, 102), (1, 105), ScLinkType.Core)

as11 = base.createAutonomousSystem(11)
scion_isd.addIsdAs(1, 11, is_core=False)
scion_isd.setCertIssuer((1, 11), 101)
as11.createNetwork('net0')
cs1 = as11.createControlService('cs1').joinNetwork('net0')
router2 = as11.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

as12 = base.createAutonomousSystem(12)
scion_isd.addIsdAs(1, 12, is_core=False)
scion_isd.setCertIssuer((1, 12), 101)
as12.createNetwork('net0')
cs1 = as12.createControlService('cs1').joinNetwork('net0')
router2 = as12.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

as13 = base.createAutonomousSystem(13)
scion_isd.addIsdAs(1, 13, is_core=False)
scion_isd.setCertIssuer((1, 13), 101)
as13.createNetwork('net0')
cs1 = as13.createControlService('cs1').joinNetwork('net0')
router2 = as13.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

as14 = base.createAutonomousSystem(14)
scion_isd.addIsdAs(1, 14, is_core=False)
scion_isd.setCertIssuer((1, 14), 101)
as14.createNetwork('net0')
cs1 = as14.createControlService('cs1').joinNetwork('net0')
router2 = as14.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

as15 = base.createAutonomousSystem(15)
scion_isd.addIsdAs(1, 15, is_core=False)
scion_isd.setCertIssuer((1, 15), 101)
as15.createNetwork('net0')
cs1 = as15.createControlService('cs1').joinNetwork('net0')
router2 = as15.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

as16 = base.createAutonomousSystem(16)
scion_isd.addIsdAs(1, 16, is_core=False)
scion_isd.setCertIssuer((1, 16), 101)
as16.createNetwork('net0')
cs1 = as16.createControlService('cs1').joinNetwork('net0')
router2 = as16.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

as17 = base.createAutonomousSystem(17)
scion_isd.addIsdAs(1, 17, is_core=False)
scion_isd.setCertIssuer((1, 17), 101)
as17.createNetwork('net0')
cs1 = as17.createControlService('cs1').joinNetwork('net0')
router2 = as17.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

as18 = base.createAutonomousSystem(18)
scion_isd.addIsdAs(1, 18, is_core=False)
scion_isd.setCertIssuer((1, 18), 101)
as18.createNetwork('net0')
cs1 = as18.createControlService('cs1').joinNetwork('net0')
router2 = as18.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

as19 = base.createAutonomousSystem(19)
scion_isd.addIsdAs(1, 19, is_core=False)
scion_isd.setCertIssuer((1, 19), 101)
as19.createNetwork('net0')
cs1 = as19.createControlService('cs1').joinNetwork('net0')
router2 = as19.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

as10 = base.createAutonomousSystem(10)
scion_isd.addIsdAs(1, 10, is_core=False)
scion_isd.setCertIssuer((1, 10), 101)
as10.createNetwork('net0')
cs1 = as10.createControlService('cs1').joinNetwork('net0')
router2 = as10.createRouter('br1')
router2.joinNetwork('net0').joinNetwork('ix151')
router2.appendStartCommand('tcset ix151 --delay=30ms --rate 5000Kbps --overwrite')

#

scion.addIxLink(151, (1, 101), (1, 18), ScLinkType.Transit)
scion.addIxLink(151, (1, 102), (1, 18), ScLinkType.Transit)
scion.addIxLink(151, (1, 102), (1, 17), ScLinkType.Transit)
scion.addIxLink(151, (1, 105), (1, 17), ScLinkType.Transit)
scion.addIxLink(151, (1, 17), (1, 11), ScLinkType.Transit)
scion.addIxLink(151, (1, 18), (1, 11), ScLinkType.Transit)
scion.addIxLink(151, (1, 18), (1, 17), ScLinkType.Transit)

#

scion.addIxLink(151, (1, 105), (1, 12), ScLinkType.Transit)
scion.addIxLink(151, (1, 103), (1, 13), ScLinkType.Transit)
scion.addIxLink(151, (1, 104), (1, 13), ScLinkType.Transit)
scion.addIxLink(151, (1, 103), (1, 14), ScLinkType.Transit)
scion.addIxLink(151, (1, 14), (1, 13), ScLinkType.Transit)
scion.addIxLink(151, (1, 12), (1, 15), ScLinkType.Transit)
scion.addIxLink(151, (1, 13), (1, 15), ScLinkType.Transit)

#

scion.addIxLink(151,   (1, 103), (1, 10), ScLinkType.Transit)
scion.addIxLink(151,   (1, 104), (1, 10), ScLinkType.Transit)
scion.addIxLink(151,   (1, 10), (1, 14), ScLinkType.Transit)
scion.addIxLink(151,   (1, 10), (1, 16), ScLinkType.Transit)
scion.addIxLink(151,   (1, 16), (1, 19), ScLinkType.Transit)
scion.addIxLink(151,   (1, 10), (1, 19), ScLinkType.Transit)
scion.addIxLink(151,   (1, 16), (1, 14), ScLinkType.Transit)
scion.addIxLink(151,   (1, 19), (1, 14), ScLinkType.Transit)

#

N = args.num_nodes

for i in range(N):
    as18 \
        .createHost(f'kubo-18-{i}') \
        .joinNetwork('net0', address=f'10.18.0.{30+i}')
    scionkubo \
        .install(f'kubo-18-{i}') \
        .setAddress(f'/scion/1-18/ip4/10.18.0.{30+i}/udp/12345/quic-v1')
    emu.addBinding(Binding(f'kubo-18-{i}',
        filter=Filter(asn=18, nodeName=f'kubo-18-{i}')))

for i in range(N):
    as19 \
        .createHost(f'kubo-19-{i}') \
        .joinNetwork('net0', address=f'10.19.0.{30+i}')
    scionkubo \
        .install(f'kubo-19-{i}') \
        .setAddress(f'/scion/1-19/ip4/10.19.0.{30+i}/udp/12345/quic-v1')
    emu.addBinding(Binding(f'kubo-19-{i}',
        filter=Filter(asn=19, nodeName=f'kubo-19-{i}')))

#

emu.addLayer(base)
emu.addLayer(routing)
emu.addLayer(ospf)
emu.addLayer(scion_isd)
emu.addLayer(scion)
emu.addLayer(ibgp)
emu.addLayer(ebgp)
emu.addLayer(scionkubo)

emu.render()

#

emu.compile(Docker(), './output', override=True)
emu.compile(Graphviz(), './graphs', override=True)

#

whales = python_on_whales.DockerClient(
    compose_files=['./output/docker-compose.yml'])
whales.compose.build(cache=True)
whales.compose.up(detach=True)

client = docker.from_env()

ctrs = {
    ctr.name: client.containers.get(ctr.id)
    for ctr in whales.compose.ps()
}

time.sleep(20)

# Set path selection strategy
for name, ctr in ctrs.items():
    if 'kubo' not in name:
        continue

    _, output = ctr.exec_run(
        '/kubo/cmd/ipfs/ipfs config --json ' +
        f'Internal.Bitswap.PathSelectionStrategy {args.path_strategy}'
    )

# Collect peer IDs
peers = dict()
for name, ctr in ctrs.items():
    if 'kubo' not in name:
        continue

    _, output = ctr.exec_run('/kubo/cmd/ipfs/ipfs id -f="<addrs>"')
    addr = output.decode('utf8').splitlines()[0]
    peers[name] = addr
file.write('peers {}\n'.format(json.dumps(peers)))

# Connect peers
for name, ctr in ctrs.items():
    if 'kubo' not in name:
        continue

    for peer_name, peer_addr in peers.items():
        if name == peer_name:
            continue

        _, output = ctr.exec_run(
            f'/kubo/cmd/ipfs/ipfs swarm connect "{peer_addr}"')
        file.write(output.decode('utf8'))

# Pick pairs to transfer content between
pairs = []
# AS18 -> AS19
pairs.extend([
    (
        f'as18h-kubo-18-{i}-10.18.0.{30+i}',
        f'as19h-kubo-19-{i}-10.19.0.{30+i}'
    )
    for i in range(N//2)
])
# AS19 -> AS18
pairs.extend([
    (
        f'as19h-kubo-19-{i}-10.19.0.{30+i}',
        f'as18h-kubo-18-{i}-10.18.0.{30+i}'
    )
    for i in range(N//2, N)
])

# Add content
retriever_cids = {}
for provider, retriever in pairs:
    _, output = ctrs[provider].exec_run([
        'bash', '-c',
        f'dd if=/dev/urandom bs=1 count={args.content_size} | '
            '/kubo/cmd/ipfs/ipfs add'
    ])
    match = re.search(r'added ([^ ]+)', output.decode('utf8'), re.MULTILINE)
    retriever_cids[retriever] = match.group(1)
file.write('content cids {}\n'.format(json.dumps(retriever_cids)))

# Retrieve content in parallel
for _, retriever in pairs:
    cid = retriever_cids[retriever]
    _, output = ctrs[retriever].exec_run([
        'bash', '-c',
        f'{{ time /kubo/cmd/ipfs/ipfs refs -r {cid} > /dev/null ; }}'
            ' 2> time.txt'
    ], detach=True)

def timeout_handler(sig, frame):
    raise Exception('timeout')

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(5 * 60) # 5 minutes

try:
    # Block till finished
    for _, retriever in pairs:
        _, output = ctrs[retriever].exec_run([
            'bash', '-c', 'tail -f time.txt | sed "/sys/ q"'
        ])

    # Collect results
    times = {}
    for _, retriever in pairs:
        _, output = ctrs[retriever].exec_run([
            'bash', '-c', 'grep -e "real" time.txt'
        ])
        times[retriever] = output.decode('utf8').splitlines()[0]
    file.write('transfer times {}\n'.format(json.dumps(times)))

    _, output = ctrs[provider_name].exec_run(
        '/kubo/cmd/ipfs/ipfs bitswap stat --verbose --human')
    file.write(output.decode('utf8'))

except Exception as e:
    file.write(f'exception {e}')

# Clean up
file.close()
whales.compose.down()
