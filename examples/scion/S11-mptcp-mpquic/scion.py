#!/usr/bin/env python3

from seedemu.compiler import Docker
from seedemu.core import Emulator
from seedemu.layers import ScionBase, ScionRouting, ScionIsd, Scion, Ebgp, Ibgp, Ospf, PeerRelationship
from seedemu.layers.Scion import LinkType as ScLinkType

# Initialize
emu = Emulator()
base = ScionBase()
routing = ScionRouting()
scion_isd = ScionIsd()
scion = Scion()
ebgp = Ebgp()
ibgp = Ibgp()
ospf = Ospf()

# SCION ISDs
base.createIsolationDomain(1)

# Internet Exchange
base.createInternetExchange(100)
base.createInternetExchange(101)

# AS-150
as150 = base.createAutonomousSystem(150)
scion_isd.addIsdAs(1, 150, is_core=True)
as150.createNetwork('net0')
as150.createNetwork('net1')
as150.createControlService('cs1').joinNetwork('net0')

as150_router = as150.createRouter('br0')
as150_router.joinNetwork('net0').joinNetwork('ix100')
as150_router1 = as150.createRouter('br1')
as150_router1.joinNetwork('net1').joinNetwork('ix101')
as150.createHost('mptcpquic').joinNetwork('net0').joinNetwork('net1').appendStartCommand("ip route add 10.151.1.0/24 via 10.150.1.254")

# AS-151
as151 = base.createAutonomousSystem(151)
scion_isd.addIsdAs(1, 151, is_core=True)
as151.createNetwork('net0')
as151.createNetwork('net1')
as151.createControlService('cs1').joinNetwork('net0')

as151_router = as151.createRouter('br0')
as151_router.joinNetwork('net0').joinNetwork('ix100')
as151_router1 = as151.createRouter('br1')
as151_router1.joinNetwork('net1').joinNetwork('ix101')
as151.createHost('mptcpquic2').joinNetwork('net0').joinNetwork('net1').appendStartCommand("ip route add 10.150.1.0/24 via 10.151.1.254")

# Inter-AS routing
#scion.addIxLink(100, (1, 150), (1, 151), ScLinkType.Core)
#scion.addIxLink(100, (1, 151), (1, 152), ScLinkType.Core)
#scion.addIxLink(100, (1, 152), (1, 150), ScLinkType.Core)
#scion.addXcLink((1, 150), (1, 153), ScLinkType.Transit)

ebgp.addPrivatePeering(100, 150, 151, abRelationship=PeerRelationship.Peer)
ebgp.addPrivatePeering(101, 150, 151, abRelationship=PeerRelationship.Peer)

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
emu.compile(Docker(), './output')
