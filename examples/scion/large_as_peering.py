#!/usr/bin/env python3

from seedemu.compiler import Docker, Graphviz
from seedemu.core import Emulator
from seedemu.layers import Base, Ospf, PeerRelationship, Routing, Scion
from seedemu.layers.Scion import LinkType as ScLinkType

# Initialize
emu = Emulator()
base = Base()
routing = Routing()
ospf = Ospf()
scion = Scion()

# SCION ISDs
scion.addIsd(1)

# Internet Exchanges
base.createInternetExchange(100)
base.createInternetExchange(101)
base.createInternetExchange(102)
base.createInternetExchange(103)

# Core AS
as150 = base.createAutonomousSystem(150)
as150.createNetwork('net0')
as150.createNetwork('net1')
as150.createNetwork('net2')
as150.createNetwork('net3')
as150_br0 = as150.createRouter('br0')
as150_br1 = as150.createRouter('br1')
as150_br2 = as150.createRouter('br2')
as150_br3 = as150.createRouter('br3')
as150_br0.joinNetwork('net0').joinNetwork('net1').joinNetwork('ix100')
as150_br1.joinNetwork('net1').joinNetwork('net2').joinNetwork('ix101')
as150_br2.joinNetwork('net2').joinNetwork('net3').joinNetwork('ix102')
as150_br3.joinNetwork('net3').joinNetwork('net0').joinNetwork('ix103')
scion.setAsIsd(150, 1)
scion.setCoreAs(150, True)

# Non-core ASes
asn_ix = {
    151: 100,
    152: 101,
    153: 101,
    154: 102,
    155: 103,
    156: 103,
}

asns = {}

for asn, ix in asn_ix.items():
    asys = base.createAutonomousSystem(asn)
    router = asys.createRouter('br0')
    asns[asn] = {"asys": asys, "router": router}
    asys.createNetwork('net0')
    router.joinNetwork('net0').joinNetwork(f'ix{ix}')
    scion.setAsIsd(asn, 1)
    scion.setCertIssuer(asn, 150)
    scion.addIxLink(ix, 150, asn, ScLinkType.Transit)

fnord = list(asns.keys())

# last InternetExchange that was created above
i = 103

for asn1, asn2 in zip(fnord, fnord[1:]+[fnord[0]]):
    i += 1
    base.createInternetExchange(i)
    asn1_router = asns[asn1]["router"]
    asn2_router = asns[asn2]["router"]

    asn1_router.joinNetwork(f'ix{i}')
    asn2_router.joinNetwork(f'ix{i}')
    scion.addIxLink(i, asn1, asn2, ScLinkType.Peer)

# Rendering
emu.addLayer(base)
emu.addLayer(routing)
emu.addLayer(ospf)
emu.addLayer(scion)

emu.render()

# Compilation
emu.compile(Docker(), './output')
emu.compile(Graphviz(), "./output/graphs")
