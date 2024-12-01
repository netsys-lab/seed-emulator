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

links = [
    (18, 11),
    (18, 17),
    (18, 102),
    (18, 101),
    (11, 17),
    (17, 102),
    (17, 105),
    (102, 101),
    (102, 104),
    (102, 103),
    (102, 105),
    (105, 101),
    (105, 12),
    (105, 103),
    (105, 104),
    (12, 15),
    (13, 15),
    (13, 104),
    (13, 103),
    (13, 14),
    (104, 101),
    (104, 103),
    (104, 10),
    (103, 101),
    (103, 10),
    (103, 14),
    (10, 14),
    (10, 19),
    (10, 16),
    (14, 16),
    (14, 19),
    (16, 19),
]
for a, b in links:
    assert (b, a) not in links

ases = set()
ases.update(a for a, _ in links)
ases.update(b for _, b in links)

tier1 = { a for a in ases if a > 100 }
tier2 = { a for a in ases if a < 100 }
is_tier1_link = lambda a, b: a in tier1 and b in tier1

#

for i, _ in enumerate(links):
    base.createInternetExchange(200 + i)

#

for asn in ases:
    as_ = base.createAutonomousSystem(asn)
    scion_isd.addIsdAs(1, asn, is_core=True)
    as_.createNetwork('net0')
    as_.createControlService('cs0').joinNetwork('net0')
    as_br0 = as_.createRouter('br0')
    as_br0.joinNetwork('net0')

    for i, (a, b) in enumerate(links):
        if a == asn or b == asn:
            as_br0.joinNetwork('ix{}'.format(200 + i))

    N = args.num_nodes

    if asn == 18 or asn == 19:
        for i in range(N):
            as_ \
                .createHost(f'kubo-{asn}-{i}') \
                .joinNetwork('net0', address=f'10.{asn}.0.{30+i}')
            scionkubo \
                .install(f'kubo-{asn}-{i}') \
                .setAddress(f'/scion/1-{asn}/ip4/10.{asn}.0.{30+i}/udp/12345/quic-v1')
            emu.addBinding(Binding(f'kubo-{asn}-{i}',
                filter=Filter(asn=asn, nodeName=f'kubo-{asn}-{i}')))

#

for i, (a, b) in enumerate(links):
    scion.addIxLink(
        200 + i,
        (1, a),
        (1, b),
        ScLinkType.Core
    )

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

#

for name, ctr in ctrs.items():
    if 'br0' not in name:
        continue

    for i, (a, b) in enumerate(links):
        if f'as{a}' not in name and f'as{b}' not in name:
            continue

        lat = 10
        bw = 15 if is_tier1_link(a, b) else 10

        _, output = ctr.exec_run([
            'bash', '-c',
            f'tc qdisc del dev ix{200+i} root &&'
            f'tc qdisc add dev ix{200+i} root netem rate {bw}mbit delay {lat}ms loss 0% &&'
            f'echo configured ix{200+i}'
        ])
        file.write(output.decode('utf8'))

#

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

    for provider, _ in pairs:
        _, output = ctrs[provider].exec_run(
            '/kubo/cmd/ipfs/ipfs bitswap stat --verbose --human')
        file.write(output.decode('utf8'))

except Exception as e:
    file.write(f'exception {e}')

# Clean up
file.close()
whales.compose.down()
