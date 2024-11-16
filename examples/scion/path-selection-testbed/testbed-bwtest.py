#!/usr/bin/env python3

import re
import time
import argparse
from pathlib import Path

import docker
import python_on_whales

from seedemu.compiler import Docker, Graphviz
from seedemu.core import Emulator, Binding, Filter
from seedemu.layers import (
    ScionBase, ScionRouting, ScionIsd, Scion, Ospf, Ibgp, Ebgp, PeerRelationship)
from seedemu.layers.Scion import LinkType as ScLinkType
from seedemu.services import Libp2pBwtestService
import json
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
bwtest = Libp2pBwtestService()

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
#sender_asn = topo['sender_asn']
#receiver_asn = topo['receiver_asn']

# Create ASes
for as__ in topo['ASes']:
    asn = as__['asn']
    isd = as__['isd']
    is_core = as__['is_core_as']
    bwserver = as__.get('bwserver', False)
    bwclient = as__.get('bwclient', False)
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
    #if asn == sender_asn:
    #    h1 = as_.createHost('h1').joinNetwork('net0')
    #    h1.addSoftware("iperf3")
    #    h1.addSoftware("python3")
    #    h1.addSoftware("python3-pip")
    #    h1.addBuildCommand('pip3 install paho-mqtt')
    #    h1.addBuildCommand('pip3 install pyyaml flask numpy')
    #    h1.addSharedFolder("/sender", "../sender")
    #    h1.addSharedFolder("/topo", "../topo")
    #if asn == receiver_asn:
    #    h1 = as_.createHost('h1').joinNetwork('net0')
    #    h1.addSoftware("iperf3")
    #    h1.addSoftware("python3")
    #    h1.addSoftware("python3-pip")
    #    h1.addBuildCommand('pip3 install paho-mqtt')
    #    h1.addBuildCommand('pip3 install pyyaml flask numpy')
    #    h1.addSharedFolder("/receiver", "../receiver")
    #    h1.addSharedFolder("/topo", "../topo")

    if bwserver:
        bwserver_host = f'bwserver-{asn}'
        bwserver_asn = asn
        bwserver_addr = f'10.{asn}.0.30'

        as_ \
            .createHost(bwserver_host) \
            .joinNetwork('net0', address=bwserver_addr)
        bwserver = bwtest.install(bwserver_host)
        emu.addBinding(Binding(bwserver_host,
            filter=Filter(asn=bwserver_asn, nodeName=bwserver_host)))

    if bwclient:
        bwclient_host = f'bwclient-{asn}'
        bwclient_asn = asn
        bwclient_addr = f'10.{asn}.0.30'

        as_ \
            .createHost(bwclient_host) \
            .joinNetwork('net0', address=bwclient_addr)
        bwclient = bwtest.install(bwclient_host)
        emu.addBinding(Binding(bwclient_host,
            filter=Filter(asn=bwclient_asn, nodeName=bwclient_host)))

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

    scion.addIxLink(id, (source_isd, source_asn), (dest_isd, dest_asn), link_type)
    ebgp.addPrivatePeering(id, source_asn, dest_asn, abRelationship=link_type_bgp)


# Rendering
emu.addLayer(base)
emu.addLayer(routing)
emu.addLayer(ospf)
emu.addLayer(scion_isd)
emu.addLayer(scion)
emu.addLayer(ibgp)
emu.addLayer(ebgp)
emu.addLayer(bwtest)

emu.render()

# Compilation
emu.compile(Docker(), './output', override=True)
emu.compile(Graphviz(), "./output/graphs", override=True)

generate_scripts(topo)

whales = python_on_whales.DockerClient(compose_files=['./output/docker-compose.yml'])
whales.compose.build(cache=True)
whales.compose.up(detach=True)

client: docker.DockerClient = docker.from_env()
ctrs = {ctr.name: client.containers.get(ctr.id) for ctr in whales.compose.ps()}

time.sleep(15)

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

# Determine hosts to use
bwserver_ctr = next((ctr for name, ctr in ctrs.items() if bwserver_host in name), None)
bwclient_ctr = next((ctr for name, ctr in ctrs.items() if bwclient_host in name), None)

# Start server
_, output = bwserver_ctr.exec_run([
    'bash', '-c',
    f'/go-libp2p/p2p/transport/scionquic/cmd/server/main 1-{bwserver_asn} '
    f'{bwserver_addr} 12345 {args.content_size} > bwserver.txt'
], detach=True)

# Wait till started
_, output = bwserver_ctr.exec_run(['bash', '-c', 'tail -f bwserver.txt | sed "/Listening/ q"'])
match = re.search(r'Listening\. Now run: .* (\/scion.*)', output.decode('utf8'), re.MULTILINE)
file.write(f'{match.group(1)}\n')

# Start client
_, output = bwclient_ctr.exec_run(
    '/go-libp2p/p2p/transport/scionquic/cmd/client/main '
    f'{match.group(1)} {args.content_size} {args.num_links}'
)
file.write(output.decode('utf8'))

whales.compose.down()
file.close()
