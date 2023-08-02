#!/usr/bin/env python3

from seedemu.compiler import Docker, Graphviz
from seedemu.core import Emulator
from seedemu.layers import (
    ScionBase, ScionRouting, ScionIsd, Scion, Ospf, Ibgp, Ebgp, PeerRelationship)
from seedemu.layers.Scion import LinkType as ScLinkType

# Initialize
emu = Emulator()
base = ScionBase()
routing = ScionRouting()
ospf = Ospf()
scion_isd = ScionIsd()
scion = Scion()
ibgp = Ibgp()
ebgp = Ebgp()

base.createIsolationDomain(1)

base.createInternetExchange(200)
base.createInternetExchange(201)
base.createInternetExchange(202)
base.createInternetExchange(203)
base.createInternetExchange(204)
base.createInternetExchange(205)
base.createInternetExchange(206)
base.createInternetExchange(207)
base.createInternetExchange(208)
base.createInternetExchange(209)

as_ixes = {
    101: [200,201,204,207],
    102: [200,202,203,209],
    103: [202,204,205,208],
    104: [201,203,205,206],
    105: [206,209],
    106: [207,208],
}

for asn, ixes in as_ixes.items():
    as_ = base.createAutonomousSystem(asn)
    is_core = True if asn == 101 or asn == 102 else False
    scion_isd.addIsdAs(1, asn, is_core=is_core)
    if not is_core:
        scion_isd.setCertIssuer((1, asn), issuer=101)
    as_.createNetwork('net0')  
    as_.createControlService('cs0').joinNetwork('net0')

    as_br0 = as_.createRouter('br0')
    as_br0.joinNetwork('net0')    
    
    as_br0.addSoftware("iperf3")
    as_br0.addSoftware("python3")
    as_br0.addSoftware("python3-pip")
    as_br0.addBuildCommand('pip3 install paho-mqtt psutil')
    
    host_port = 9000+asn
    node_port = 5000
    # as_br0.addPortForwarding(host_port, node_port)
    as_br0.addSharedFolder("/node", "../node")
    for ix in ixes:
        as_br0.joinNetwork('ix{}'.format(ix))
    
    if asn == 106 or asn == 105:
        as_.createHost('h1').joinNetwork('net0')


h1_106 = base.getAutonomousSystem(106).getHost('h1')
h1_106.setDisplayName('Machine')
h1_106.addSoftware("iperf3")
h1_106.addSoftware("ffmpeg mpv")
h1_106.addSoftware("mosquitto")
h1_106.addSoftware("python3")
h1_106.addSoftware("python3-pip")
h1_106.addBuildCommand('pip3 install paho-mqtt')
h1_106.addBuildCommand('pip3 install psutil pyserial pygame requests numpy deap')
h1_106.addBuildCommand('pip3 install dash dash-cytoscape dash-bootstrap-components dash-daq')
h1_106.addSharedFolder("/dmtp", "../dmtp_server")
h1_106.addPortForwarding(1883, 1883)


h1_105 = base.getAutonomousSystem(105).getHost('h1')
h1_105.setDisplayName('Operator')
h1_105.addSoftware("iperf3")
h1_105.addSoftware("ffmpeg mpv")
h1_105.addSoftware("mosquitto-clients")
h1_105.addSoftware("python3")
h1_105.addSoftware("python3-pip")
h1_105.addBuildCommand('pip3 install paho-mqtt')
h1_105.addBuildCommand('pip3 install psutil pygame requests numpy deap')
h1_105.addBuildCommand('pip3 install dash dash-cytoscape dash-bootstrap-components dash-daq')
h1_105.addSharedFolder("/dmtp", "../dmtp_client")
h1_105.addSharedFolder("/server", "../dmtp_server")

# SCION links
scion.addIxLink(200, (1, 101), (1, 102), ScLinkType.Core)
scion.addIxLink(204, (1, 101), (1, 103), ScLinkType.Transit)
scion.addIxLink(201, (1, 101), (1, 104), ScLinkType.Transit)
scion.addIxLink(207, (1, 101), (1, 106), ScLinkType.Transit)
scion.addIxLink(202, (1, 102), (1, 103), ScLinkType.Transit)
scion.addIxLink(203, (1, 102), (1, 104), ScLinkType.Transit)
scion.addIxLink(209, (1, 102), (1, 105), ScLinkType.Transit)
scion.addIxLink(205, (1, 104), (1, 103), ScLinkType.Transit)
scion.addIxLink(206, (1, 104), (1, 105), ScLinkType.Transit)
scion.addIxLink(208, (1, 103), (1, 106), ScLinkType.Transit)

# BGP links
ebgp.addPrivatePeering(200, 101, 102, abRelationship=PeerRelationship.Peer)
ebgp.addPrivatePeering(201, 101, 104, abRelationship=PeerRelationship.Provider)
ebgp.addPrivatePeering(204, 101, 103, abRelationship=PeerRelationship.Provider)
ebgp.addPrivatePeering(207, 101, 106, abRelationship=PeerRelationship.Provider)
ebgp.addPrivatePeering(202, 102, 103, abRelationship=PeerRelationship.Provider)
ebgp.addPrivatePeering(203, 102, 104, abRelationship=PeerRelationship.Provider)
ebgp.addPrivatePeering(209, 102, 105, abRelationship=PeerRelationship.Provider)
ebgp.addPrivatePeering(205, 104, 103, abRelationship=PeerRelationship.Provider)
ebgp.addPrivatePeering(206, 104, 105, abRelationship=PeerRelationship.Provider)
ebgp.addPrivatePeering(208, 103, 106, abRelationship=PeerRelationship.Provider)


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

