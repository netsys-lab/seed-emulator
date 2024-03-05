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

# ASN Mapping
bgpAsnToSCION = {
    10: "71-2:0:35", # BRIDGES Core
    11: "71-20965", # Geant Core
    12: "71-20966", # Geant Core

    100: "71-2:0:48", # Equinix
    101: "71-225", # Uva
    102: "71-88", # Princeton
    103: "71-2:0:49", # Cybexer
    104: "71-1140", # SIDN Labs
    105: "71-2:0:4a", # Ovgu 
    106: "71-2546", # Demokritos
}

# SCION ISDs
base.createIsolationDomain(71)

# Internet Exchange TODO: Currently only 150 is used because of some issues with multiple IXes
base.createInternetExchange(150) # US Internal
base.createInternetExchange(151) # US-Europe
base.createInternetExchange(152) # Europe Internal
base.createInternetExchange(153) # Europe-KISTI
base.createInternetExchange(154) # KISTI Internal

# Bridges Core (currently only one node)
bridgesCore = base.createAutonomousSystem(10)
scion_isd.addIsdAs(71, 10, is_core=True)
bridgesCore.createNetwork('net0')
bridgesCore.createControlService('cs1').joinNetwork('net0')
bridgesCore_router = bridgesCore.createRouter('br0')
bridgesCore_router.joinNetwork('net0').joinNetwork('ix150')#.joinNetwork('ix150').
#bridgesCore_router2 = bridgesCore.createRouter('br1')
#bridgesCore_router2.joinNetwork('net0').joinNetwork('ix151')

# GEANT Core
geantCore = base.createAutonomousSystem(11)
scion_isd.addIsdAs(71, 11, is_core=True)
geantCore.createNetwork('net0')
geantCore.createControlService('cs1').joinNetwork('net0')
geantCore_router1 = geantCore.createRouter('br0')
geantCore_router1.joinNetwork('net0').joinNetwork('ix150')
#geantCore_router2 = geantCore.createRouter('br1')
#geantCore_router2.joinNetwork('net0').joinNetwork('ix152')
#geantCore_router3 = geantCore.createRouter('br2')
#geantCore_router3.joinNetwork('net0').joinNetwork('ix153')

# Connect Bridges / GEANT TODO: More than one link does not work...
scion.addIxLink(150, (71, 10), (71, 11), ScLinkType.Core)
# scion.addIxLink(151, (71, 10), (71, 11), ScLinkType.Core)

# Equinix AS
equinix = base.createAutonomousSystem(100)
scion_isd.addIsdAs(71, 100)
scion_isd.setCertIssuer((71, 100), issuer=10)
equinix.createNetwork('net0')
equinix.createControlService('cs1').joinNetwork('net0')
equinix_router1 = equinix.createRouter('br0')
equinix_router1.joinNetwork('net0').joinNetwork('ix150')
scion.addIxLink(150, (71, 10), (71, 100), ScLinkType.Transit)

# UVA
uva = base.createAutonomousSystem(101)
scion_isd.addIsdAs(71, 101)
scion_isd.setCertIssuer((71, 101), issuer=10)
uva.createNetwork('net0')
uva.createControlService('cs1').joinNetwork('net0')
uva_router1 = uva.createRouter('br0')
uva_router1.joinNetwork('net0').joinNetwork('ix150')
scion.addIxLink(150, (71, 10), (71, 101), ScLinkType.Transit)

# Princeton
princeton = base.createAutonomousSystem(102)
scion_isd.addIsdAs(71, 102)
scion_isd.setCertIssuer((71, 102), issuer=10)
princeton.createNetwork('net0')
princeton.createControlService('cs1').joinNetwork('net0')
princeton_router1 = princeton.createRouter('br0')
princeton_router1.joinNetwork('net0').joinNetwork('ix150')
scion.addIxLink(150, (71, 10), (71, 102), ScLinkType.Transit)

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
