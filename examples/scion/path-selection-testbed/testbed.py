#!/usr/bin/env python3

from seedemu.compiler import Docker, Graphviz
from seedemu.core import Emulator
from seedemu.layers import (
    ScionBase, ScionRouting, ScionIsd, Scion, Ospf, Ibgp, Ebgp, PeerRelationship)
from seedemu.layers.Scion import LinkType as ScLinkType
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

# load topo.json to dict
topo = json.load(open('topo/topo.json'))

# Create isolation domains
for isd in topo['ISDs']:
    base.createIsolationDomain(isd)

# Create ixs
for link in topo['links']:
    base.createInternetExchange(link['id'])

dashboard_asn = topo['dashboard_asn']
sender_asn = topo['sender_asn']
receiver_asn = topo['receiver_asn']
# Create ASes
for as__ in topo['ASes']:
    asn = as__['asn']
    isd = as__['isd']
    is_core = as__['is_core_as']
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
    if asn == sender_asn:
        h1 = as_.createHost('h1').joinNetwork('net0')  
        h1.addSoftware("iperf3")
        h1.addSoftware("python3")
        h1.addSoftware("python3-pip")
        h1.addBuildCommand('pip3 install paho-mqtt')
        h1.addBuildCommand('pip3 install pyyaml')
        h1.addSharedFolder("/sender", "../sender")
        h1.addSharedFolder("/topo", "../topo")
    if asn == receiver_asn:
        h1 = as_.createHost('h1').joinNetwork('net0')  
        h1.addSoftware("iperf3")
        h1.addSoftware("python3")
        h1.addSoftware("python3-pip")
        h1.addBuildCommand('pip3 install paho-mqtt')
        h1.addBuildCommand('pip3 install pyyaml')
        h1.addSharedFolder("/receiver", "../receiver")
        h1.addSharedFolder("/topo", "../topo")


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

emu.render()

# Compilation
emu.compile(Docker(), './output', override=True)
emu.compile(Graphviz(), "./output/graphs", override=True)

generate_scripts(topo)