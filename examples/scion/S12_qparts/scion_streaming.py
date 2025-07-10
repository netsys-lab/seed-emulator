#!/usr/bin/env python3
# encoding: utf-8


from seedemu.services import GolangDevService, AccessMode
from seedemu.core import Emulator, Binding, Filter

from seedemu.compiler import Docker
from seedemu.core import Emulator, OptionRegistry
from seedemu.layers import ScionBase, ScionRouting, ScionIsd, Scion, CheckoutSpecification, SetupSpecification
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
    spec = SetupSpecification.LOCAL_BUILD(
            CheckoutSpecification(
                mode = "build",
                git_repo_url = "https://github.com/scionproto/scion.git",
                checkout = "v0.12.0" # could be tag, branch or commit-hash
            ))
    routing = ScionRouting(setup_spec=OptionRegistry().scion_setup_spec(spec))
    scion_isd = ScionIsd()
    scion = Scion()

    devsvc = GolangDevService('jane.doe', 'jane.doe@example.com') # TODO: Put credentials here
    repo_url = 'https://github.com/netsys-lab/qparts.git'
    repo_branch = 'feature/streaming'
    repo_path = '/home/root/repos/scion'



    # SCION ISDs
    base.createIsolationDomain(1)

    # Internet Exchange
    base.createInternetExchange(100, create_rs=False)

    # AS-160
    as160 = base.createAutonomousSystem(160)
    scion_isd.addIsdAs(1, 160, is_core=True)
    as160.createNetwork('net0')
    as160.createControlService('cs1').joinNetwork('net0')
    as160_router = as160.createRealWorldRouter('br0', prefixes=['0.0.0.0/1', '128.0.0.0/1'])
    # expectation: hosts from within AS160 can ping outside world i.e. 8.8.8.8
    #   Hosts in the other ASes can't!!
    as160_router.joinNetwork('net0').joinNetwork('ix100')
    as160_router.crossConnect(163, 'br0', '10.50.0.2/29')

    # AS-161
    as161 = base.createAutonomousSystem(161)
    scion_isd.addIsdAs(1, 161, is_core=True)
    as161.createNetwork('net0')
    as161.createControlService('cs1').joinNetwork('net0')
    as161.createRouter('br0').joinNetwork('net0').joinNetwork('ix100')

    # AS-162
    as162 = base.createAutonomousSystem(162)
    scion_isd.addIsdAs(1, 162, is_core=True)
    as162.createNetwork('net0')
    as162_cs1 = as162.createControlService('cs1').joinNetwork('net0')
    as162.createRouter('br0').joinNetwork('net0').joinNetwork('ix100')

    # AS-163
    as163 = base.createAutonomousSystem(163)
    scion_isd.addIsdAs(1, 163, is_core=False)
    scion_isd.setCertIssuer((1, 163), issuer=160)
    as163.createNetwork('net0')
    as163_cs1 = as163.createControlService('cs1').joinNetwork('net0')

    as163_router = as163.createRouter('br0')
    as163_router.joinNetwork('net0')
    as163_router.crossConnect(160, 'br0', '10.50.0.3/29')

    # Inter-AS routing
    scion.addIxLink(100, (1, 160), (1, 161), ScLinkType.Core)
    scion.addIxLink(100, (1, 161), (1, 162), ScLinkType.Core)
    scion.addIxLink(100, (1, 162), (1, 160), ScLinkType.Core)
    scion.addXcLink((1, 160), (1, 163), ScLinkType.Transit)

    svc = devsvc.install(f'dev_162_cs1')
    svc.checkoutRepo(repo_url, repo_path, repo_branch, AccessMode.shared)
    emu.addBinding(Binding(f'dev_162_cs1', filter=Filter(nodeName=as162_cs1.getName(), asn=162)))

    svc3 = devsvc.install(f'dev_163_cs1')
    svc3.checkoutRepo(repo_url, repo_path, repo_branch, AccessMode.shared)
    emu.addBinding(Binding(f'dev_163_cs1', filter=Filter(nodeName=as163_cs1.getName(), asn=163)))

    # Rendering
    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(scion_isd)
    emu.addLayer(scion)
    emu.addLayer(devsvc)


    if dumpfile is not None:
        emu.dump(dumpfile)
    else:
        emu.render()

        ###############################################################################
        # Compilation

        emu.compile(Docker(platform=platform), './output', override=True)

if __name__ == "__main__":
    run()