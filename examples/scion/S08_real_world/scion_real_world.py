#!/usr/bin/env python3
# encoding: utf-8

#from seedemu.layers import Base, Routing, Ebgp, PeerRelationship, Ibgp, Ospf
#from seedemu.services import WebService
from seedemu.core import Emulator, Binding, Filter
#from seedemu.raps import OpenVpnRemoteAccessProvider
  
from seedemu.compiler import Docker
from seedemu.core import Emulator
from seedemu.layers import ScionBase, ScionRouting, ScionIsd, Scion
from seedemu.layers.Scion import LinkType as ScLinkType

from seedemu.compiler import Docker, Platform
import os, sys

def run(dumpfile = None):
    ###############################################################################
    # Set the platform information
    if dumpfile is None:
        script_name = os.path.basename(__file__)

        if len(sys.argv) == 1:
            platform = Platform.AMD64
        elif len(sys.argv) == 2:
            if sys.argv[1].lower() == 'amd':
                platform = Platform.AMD64
            elif sys.argv[1].lower() == 'arm':
                platform = Platform.ARM64
            else:
                print(f"Usage:  {script_name} amd|arm")
                sys.exit(1)
        else:
            print(f"Usage:  {script_name} amd|arm")
            sys.exit(1)
    
    # Initialize
    emu = Emulator()
    base = ScionBase()
    routing = ScionRouting()
    scion_isd = ScionIsd()
    scion = Scion()

    # SCION ISDs
    base.createIsolationDomain(1)

    # Internet Exchange
    base.createInternetExchange(100, create_rs=False)

    # AS-150
    as150 = base.createAutonomousSystem(150)
    scion_isd.addIsdAs(1, 150, is_core=True)
    as150.createNetwork('net0')# .enableRealWorld() ^^ thats we'd like to do . . .
    as150.createControlService('cs1').joinNetwork('net0')
    as150_router = as150.createRealWorldRouter('br0', prefixes=['10.150.0.0/24'])# the 'auto' gen prefix of net0
    # expectation: hosts from within AS150 can ping outside world i.e. 8.8.8.8
    #   Hosts in the other ASes can't!!
    as150_router.joinNetwork('net0').joinNetwork('ix100')
    as150_router.crossConnect(153, 'br0', '10.50.0.2/29')

    # AS-151
    as151 = base.createAutonomousSystem(151)
    scion_isd.addIsdAs(1, 151, is_core=True)
    as151.createNetwork('net0')
    as151.createControlService('cs1').joinNetwork('net0')
    as151.createRouter('br0').joinNetwork('net0').joinNetwork('ix100')

    # AS-152
    as152 = base.createAutonomousSystem(152)
    scion_isd.addIsdAs(1, 152, is_core=True)
    as152.createNetwork('net0')
    as152.createControlService('cs1').joinNetwork('net0')
    as152.createRouter('br0').joinNetwork('net0').joinNetwork('ix100')

    # AS-153
    as153 = base.createAutonomousSystem(153)
    scion_isd.addIsdAs(1, 153, is_core=False)
    scion_isd.setCertIssuer((1, 153), issuer=150)
    as153.createNetwork('net0')
    as153.createControlService('cs1').joinNetwork('net0')
    as153_router = as153.createRouter('br0')
    as153_router.joinNetwork('net0')
    as153_router.crossConnect(150, 'br0', '10.50.0.3/29')

    # Inter-AS routing
    scion.addIxLink(100, (1, 150), (1, 151), ScLinkType.Core)
    scion.addIxLink(100, (1, 151), (1, 152), ScLinkType.Core)
    scion.addIxLink(100, (1, 152), (1, 150), ScLinkType.Core)
    scion.addXcLink((1, 150), (1, 153), ScLinkType.Transit)

    # Rendering
    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(scion_isd)
    emu.addLayer(scion)



    if dumpfile is not None:
        emu.dump(dumpfile)
    else:
        emu.render()

        ###############################################################################
        # Compilation 

        emu.compile(Docker(platform=platform), './output', override=True)

if __name__ == "__main__":
    run()