#!/usr/bin/env python3

from seedemu.compiler import Docker
from seedemu.core import Emulator
from seedemu.layers import ScionBase, ScionRouting, ScionIsd, Scion, Ebgp, PeerRelationship, ScionSbas
from seedemu.layers.Scion import LinkType as ScLinkType

# Initialize
emu = Emulator()
base = ScionBase()
routing = ScionRouting()
scion_isd = ScionIsd()
scion = Scion()
ebgp = Ebgp()
sbas = ScionSbas()

# SCION ISDs
base.createIsolationDomain(1)

# Internet Exchange
base.createInternetExchange(100)
base.createInternetExchange(101)
base.createInternetExchange(102)
base.createInternetExchange(103)


# AS-151
as151 = base.createAutonomousSystem(151)
scion_isd.addIsdAs(1, 151, is_core=True)
as151.createNetwork('net0')
as151.createRouter('br0').joinNetwork('net0').joinNetwork('ix101')

# AS-153
as153 = base.createAutonomousSystem(153)
scion_isd.addIsdAs(1, 153, is_core=True)
as153.createNetwork('net0')
as153.createRouter('br0').joinNetwork('net0').joinNetwork('ix102')

# AS-155
as155 = base.createAutonomousSystem(155)
scion_isd.addIsdAs(1, 155, is_core=True)
as155.createNetwork('net0')
as155.createRouter('br0').joinNetwork('net0').joinNetwork('ix103')

# AS-152 rechts oben
as152 = base.createAutonomousSystem(152)
scion_isd.addIsdAs(1, 152, is_core=True)
as152.createNetwork('net0')
cs1 = as152.createControlService('cs1').joinNetwork('net0')
as152.createRouter('br0').joinNetwork('net0').joinNetwork('ix100')
as152_router2 = as152.createRouter('br1')
as152_router2.joinNetwork('net0').joinNetwork('ix102')

# AS-152 rechts oben
as154 = base.createAutonomousSystem(154)
scion_isd.addIsdAs(1, 154, is_core=True)
as154.createNetwork('net0')
cs1 = as154.createControlService('cs1').joinNetwork('net0')
as154.createRouter('br0').joinNetwork('net0').joinNetwork('ix100')
as154_router2 = as154.createRouter('br1')
as154_router2.joinNetwork('net0').joinNetwork('ix103')

# AS-150 links oben
as150 = base.createAutonomousSystem(150)
scion_isd.addIsdAs(1, 150, is_core=True)
as150.createNetwork('net0')
cs1 = as150.createControlService('cs1').joinNetwork('net0')
as150_router = as150.createRouter('br0')
as150_router.joinNetwork('net0').joinNetwork('ix100')
as150_router2 = as150.createRouter('br1')
as150_router2.joinNetwork('net0').joinNetwork('ix101')

# Inter-AS routing
scion.addIxLink(100, (1, 150), (1, 152), ScLinkType.Core)
scion.addIxLink(100, (1, 150), (1, 154), ScLinkType.Core)
scion.addIxLink(100, (1, 152), (1, 154), ScLinkType.Core)

ebgp.addPrivatePeering(101, 150, 151, abRelationship=PeerRelationship.Peer)
ebgp.addPrivatePeering(102, 152, 153, abRelationship=PeerRelationship.Peer)
ebgp.addPrivatePeering(103, 154, 155, abRelationship=PeerRelationship.Peer)

# TODO: Support for multiple Sbas instances, announce proper ASN to neighbour BGP routers
sbas.setAsn(160)

# Fetch IX links and networks etc from AS 
# configuration to make it as easy as possible here...
sbas.addPop(150)
sbas.addPop(152)
sbas.addPop(154)

# Add customer, this also reuses the IX links and 
# networks etc from AS configuration
# First argument is the pop, second the customer and the last one the IX at which customer and pop connect
sbas.addCustomer(150, 151, 101)
sbas.addCustomer(152, 153, 102)
sbas.addCustomer(154, 155, 103)

# Rendering
emu.addLayer(base)
emu.addLayer(sbas)
emu.addLayer(routing)
emu.addLayer(scion_isd)
emu.addLayer(scion)
emu.addLayer(ebgp)
emu.render()

# Compilation
emu.compile(Docker(), './output')
