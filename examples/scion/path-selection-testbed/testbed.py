#!/usr/bin/env python3

import re
import time
import argparse
import json
import signal
from pathlib import Path

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
from generate_scripts import generate_scripts

# Initialize
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
parser.add_argument('--num-links', type=int, required=True)
parser.add_argument('--link-latency', type=int, required=True)
parser.add_argument('--link-bandwidth', type=int, required=True)
parser.add_argument('--content-size', type=int, required=True)
parser.add_argument('--output-file', type=Path, required=True)
args = parser.parse_args()

# Open file to write results
file = open(args.output_file, mode='w', encoding='utf-8')
file.write(
    'num_links={}, link_latency={}, '.format(
        args.num_links, args.link_latency) +
    'link_bandwidth={}, content_size={}'.format(
        args.link_bandwidth, args.content_size) +
    '\n'
)

# Build topology
topo = {
    'ISDs' : [1],
    'ASes' : [
        {
            'asn' : 101,
            'isd' : 1,
            'label' : '101',
            'is_core_as' : True,
            'kubos': 1,
            'bwserver': True,
        },
        {
            'asn' : 102,
            'isd' : 1,
            'label' : '102',
            'is_core_as' : True,
            'kubos': 1,
            'bwclient': True,
        },
    ],
    'links' : [],
    'dashboard_asn' : 101,
    'sender_asn' : 101,
    'receiver_asn' : 102,
}

for i in range(args.num_links):
    topo['links'].append({
        'id' : 200 + i,
        'is_core_link' : True,
        'source_asn' : 101,
        'dest_asn' : 102,
        'latency': args.link_latency,
        'bandwidth': args.link_bandwidth,
    })

# Create isolation domains
for isd in topo['ISDs']:
    base.createIsolationDomain(isd)

# Create ixs
for link in topo['links']:
    base.createInternetExchange(link['id'])

dashboard_asn = topo['dashboard_asn']

# Create ASes
for as__ in topo['ASes']:
    asn = as__['asn']
    isd = as__['isd']
    is_core = as__['is_core_as']
    kubos = as__['kubos']
    as_ = base.createAutonomousSystem(asn)
    scion_isd.addIsdAs(isd, asn, is_core=is_core)
    if not is_core:
        issuer = as__['cert_issuer']
        scion_isd.setCertIssuer((isd, asn), issuer=issuer)

    as_.createNetwork('net0')
    as_.createControlService('cs0').joinNetwork('net0')
    as_br0 = as_.createRouter('br0')
    as_br0.joinNetwork('net0')
    as_br0.addSoftware("iperf3")
    as_br0.addSoftware("python3")
    as_br0.addSoftware("python3-pip")
    as_br0.addBuildCommand('pip3 install paho-mqtt psutil')
    as_br0.addSharedFolder("/node", "../node")

    ixes = [link['id'] for link in topo['links'] if link['source_asn'] == asn or link['dest_asn'] == asn]
    for ix in ixes:
        as_br0.joinNetwork('ix{}'.format(ix))

    if asn == dashboard_asn:
        h1 = as_.createHost('h1').joinNetwork('net0')
        h1.addSoftware("iperf3")
        h1.addSoftware("mosquitto")
        h1.addSoftware("python3")
        h1.addSoftware("python3-pip")
        h1.addBuildCommand('pip3 install paho-mqtt')
        h1.addBuildCommand('pip3 install psutil pyserial pygame requests numpy deap token-bucket')
        h1.addBuildCommand('pip3 install dash dash-cytoscape dash-bootstrap-components dash-daq')
        h1.addPortForwarding(1883, 1883)
        h1.addPortForwarding(8050, 8050)
        h1.addSharedFolder("/topo", "../topo")
        h1.addSharedFolder("/dashboard", "../dashboard")

    # Create kubo nodes
    for i in range(kubos):
        as_ \
            .createHost(f'kubo-{asn}-{i}') \
            .joinNetwork('net0', address=f'10.{asn}.0.{30+i}')
        kubo = scionkubo.install(f'kubo-{asn}-{i}')
        kubo.setAddress(
            f'/scion/1-{asn}/ip4/10.{asn}.0.{30+i}/udp/12345/quic-v1')
        emu.addBinding(Binding(f'kubo-{asn}-{i}',
            filter=Filter(asn=asn, nodeName=f'kubo-{asn}-{i}')))

# add scion and bgp links
for link in topo['links']:
    id = link['id']
    source_asn = link['source_asn']
    source_isd  = 1
    for as__ in topo['ASes']:
        if as__['asn'] == source_asn:
            source_isd = as__['isd']
            break
    dest_isd = 1
    for as__ in topo['ASes']:
        if as__['asn'] == link['dest_asn']:
            dest_isd = as__['isd']
            break

    dest_asn = link['dest_asn']
    link_type = ScLinkType.Transit
    link_type_bgp = PeerRelationship.Provider
    if link['is_core_link'] == True:
        link_type = ScLinkType.Core
        link_type_bgp = PeerRelationship.Peer

    scion.addIxLink(
        id,
        (source_isd, source_asn),
        (dest_isd, dest_asn),
        link_type
    )
    ebgp.addPrivatePeering(
        id, source_asn, dest_asn, abRelationship=link_type_bgp)


# Rendering
emu.addLayer(base)
emu.addLayer(routing)
emu.addLayer(ospf)
emu.addLayer(scion_isd)
emu.addLayer(scion)
emu.addLayer(ibgp)
emu.addLayer(ebgp)
emu.addLayer(scionkubo)

emu.render()

# Compilation
emu.compile(Docker(), './output', override=True)
emu.compile(Graphviz(), './output/graphs', override=True)

generate_scripts(topo)

whales = python_on_whales.DockerClient(
    compose_files=['./output/docker-compose.yml'])
whales.compose.build(cache=True)
whales.compose.up(detach=True)

client: docker.DockerClient = docker.from_env()
ctrs = {
    ctr.name: client.containers.get(ctr.id)
    for ctr in whales.compose.ps()
}

time.sleep(10)

# Configure links
for name, ctr in ctrs.items():
    if 'br0' not in name:
        continue

    for link in topo['links']:
        id, bw, lat = link['id'], link['bandwidth'], link['latency']
        _, output = ctr.exec_run([
            'bash', '-c',
            f'tc qdisc del dev ix{id} root &&'
            f'tc qdisc add dev ix{id} root netem rate {bw}mbit delay {lat}ms loss 0% &&'
            f'echo configured ix{id}'
        ])
        file.write(output.decode('utf8'))

# Set path selection strategy
for name, ctr in ctrs.items():
    if 'kubo' not in name:
        continue

    _, output = ctr.exec_run(
        '/kubo/cmd/ipfs/ipfs config --json ' +
        'Internal.Bitswap.PathSelectionStrategy 1'
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

# Determine peers to use
provider_name = next(
    (
        name for name, _ in peers.items()
        if 'kubo-101-0' in name
    ),
    None
)
assert provider_name is not None
retriever_names = [
    name for name, _ in peers.items()
    if 'kubo-102-' in name
]
assert len(retriever_names) > 0

# Add content
retriever_cids = {}
for retriever_name in retriever_names:
    _, output = ctrs[provider_name].exec_run([
        'bash', '-c',
        f'dd if=/dev/urandom bs=1 count={args.content_size} | '
            '/kubo/cmd/ipfs/ipfs add'
    ])
    match = re.search(r'added ([^ ]+)', output.decode('utf8'), re.MULTILINE)
    retriever_cids[retriever_name] = match.group(1)
file.write('content cids {}\n'.format(json.dumps(retriever_cids)))

# Retrieve content in parallel
for retriever_name in retriever_names:
    cid = retriever_cids[retriever_name]
    _, output = ctrs[retriever_name].exec_run([
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
    for retriever_name in retriever_names:
        _, output = ctrs[retriever_name].exec_run([
            'bash', '-c', 'tail -f time.txt | sed "/sys/ q"'
        ])

    # Collect results
    times = {}
    for retriever_name in retriever_names:
        _, output = ctrs[retriever_name].exec_run([
            'bash', '-c', 'grep -e "real" time.txt'
        ])
        times[retriever_name] = output.decode('utf8').splitlines()[0]
    file.write('transfer times {}\n'.format(json.dumps(times)))

    _, output = ctrs[provider_name].exec_run(
        '/kubo/cmd/ipfs/ipfs bitswap stat --verbose --human')
    file.write(output.decode('utf8'))
except Exception as e:
    file.write(f'exception {e}')

# Clean up
file.close()
whales.compose.down()
