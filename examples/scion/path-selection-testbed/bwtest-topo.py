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
from seedemu.services import Libp2pBwtestService

#

emu = Emulator()
base = ScionBase()
routing = ScionRouting()
ospf = Ospf()
scion_isd = ScionIsd()
scion = Scion()
ibgp = Ibgp()
ebgp = Ebgp()
bwtest = Libp2pBwtestService()

#

parser = argparse.ArgumentParser(__package__)
parser.add_argument('--num-paths', type=int, required=True)
parser.add_argument('--content-size', type=int, required=True)
parser.add_argument('--output-file', type=pathlib.Path, required=True)
args = parser.parse_args()

file = open(args.output_file, mode='w', encoding='utf-8')
file.write(
    'num_paths={}, content_size={}\n'.format(
        args.num_paths, args.content_size)
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

    if asn == 18:
        as_ \
            .createHost('bwserver-18-0') \
            .joinNetwork('net0', address='10.18.0.30')
        bwtest.install('bwserver-18-0')
        emu.addBinding(Binding('bwserver-18-0',
            filter=Filter(asn=18, nodeName='bwserver-18-0')))

    if asn == 19:
        as_ \
            .createHost('bwclient-19-0') \
            .joinNetwork('net0', address='10.19.0.30')
        bwtest.install('bwclient-19-0')
        emu.addBinding(Binding('bwclient-19-0',
            filter=Filter(asn=19, nodeName='bwclient-19-0')))

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
emu.addLayer(bwtest)

emu.render()

#

emu.compile(Docker(), './output', override=True)
emu.compile(Graphviz(), './graphs', override=True)

#

whales = python_on_whales.DockerClient(
    compose_files=['./output/docker-compose.yml'])
whales.compose.build(cache=False)
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

srvname = 'as18h-bwserver-18-0-10.18.0.30'
cliname = 'as19h-bwclient-19-0-10.19.0.30'

# Start server
_, output = ctrs[srvname].exec_run([
    'bash', '-c',
    '/go-libp2p/p2p/transport/scionquic/cmd/server/main 1-18 '
    f'10.18.0.30 12345 {args.content_size} > bwserver.txt'
], detach=True)

# Wait till started
_, output = ctrs[srvname].exec_run([
    'bash', '-c', 'tail -f bwserver.txt | sed "/Listening/ q"'])
match = re.search(
    r'Listening\. Now run: .* (\/scion.*)',
    output.decode('utf8'), re.MULTILINE
)
file.write(f'{match.group(1)}\n')

# Start client
_, output = ctrs[cliname].exec_run(
    '/go-libp2p/p2p/transport/scionquic/cmd/client/main '
    f'{match.group(1)} {args.content_size} {args.num_paths}'
)
file.write(output.decode('utf8'))

# Clean up
file.close()
whales.compose.down()
