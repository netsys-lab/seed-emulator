#!/usr/bin/env python3

from seedemu.compiler import Docker
from seedemu.core import Emulator
from seedemu.layers import ScionBase, ScionRouting, ScionIsd, Scion, Ebgp, PeerRelationship
from seedemu.layers.Scion import LinkType as ScLinkType

# Initialize
emu = Emulator()
base = ScionBase()
routing = ScionRouting()
scion_isd = ScionIsd()
scion = Scion()
ebgp = Ebgp()

# SCION ISDs
base.createIsolationDomain(1)

# Internet Exchange
base.createInternetExchange(100)
base.createInternetExchange(101)

# AS-150 links oben
as150 = base.createAutonomousSystem(150)
scion_isd.addIsdAs(1, 150, is_core=True)
as150.createNetwork('net0')
cs1 = as150.createControlService('cs1').joinNetwork('net0')
# Route outgoing sig traffic to SIG/CS
cs1.appendStartCommand("ip route add 10.101.0.0/24 via 10.150.0.253")
cs1.appendStartCommand("ip route add 10.151.0.0/24 via 10.150.0.253")
as150_router = as150.createRouter('br0')
as150_router.joinNetwork('net0').joinNetwork('ix100')

as150_router2 = as150.createRouter('br1')
# 10.150.0.71 is the SIG here
bgp_tmpl = """
protocol static staticroutes {
    ipv4 {
        table t_bgp;
    };
    route 10.152.0.0/24 via 10.150.0.71 { bgp_large_community.add(LOCAL_COMM); };
}
"""


as150_router2.appendStartCommand('echo "{}" >> /etc/bird/bird.conf'.format(bgp_tmpl))#.appendStartCommand("birdc configure")
# Announce AS-152 prefix to other peers in ix101, route to SIG/CS
as150_router2.joinNetwork('net0').joinNetwork('ix101')# .addStaticRoute("", "")

# AS-151
as151 = base.createAutonomousSystem(151)
scion_isd.addIsdAs(1, 151, is_core=True)
as151.createNetwork('net0')
as151.createRouter('br0').joinNetwork('net0').joinNetwork('ix101')


# AS-152
as152 = base.createAutonomousSystem(152)
scion_isd.addIsdAs(1, 152, is_core=True)
as152.createNetwork('net0')
cs1 = as152.createControlService('cs1').joinNetwork('net0')
as152.createRouter('br0').joinNetwork('net0').joinNetwork('ix100')

# AS-153
#as153 = base.createAutonomousSystem(153)
#scion_isd.addIsdAs(1, 153, is_core=False)
#scion_isd.setCertIssuer((1, 153), issuer=150)
#as153.createNetwork('net0')
#as153.createControlService('cs1').joinNetwork('net0')
#as153_router = as153.createRouter('br0')
#as153_router.joinNetwork('net0')
#as153_router.crossConnect(150, 'br0', '10.50.0.3/29')

# Inter-AS routing
scion.addIxLink(100, (1, 150), (1, 152), ScLinkType.Core)

# Configure IP Gateways
as150.createSig("sig-1", "10.150.0.0/24", "10.150.0.71")
as152.createSig("sig-1", "10.152.0.0/24", "10.152.0.71",)

# Connect IP Gateways
as150.connectSig("sig-1", ["10.152.0.0/24"], "1-152")
as152.connectSig("sig-1", ["10.150.0.0/24", "10.151.0.0/24", "10.101.0.0/24"], "1-150")

ebgp.addPrivatePeering(101, 150, 151, abRelationship=PeerRelationship.Peer)

# Rendering
emu.addLayer(base)
emu.addLayer(routing)
emu.addLayer(scion_isd)
emu.addLayer(scion)
emu.addLayer(ebgp)
emu.render()

# Compilation
emu.compile(Docker(), './output')
