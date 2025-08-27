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

    devsvc = GolangDevService('jane.doe', 'jane.doe@example.com')
    repo_url = 'https://github.com/scionproto/scion.git'
    repo_branch = 'v0.12.0'
    repo_path = '/home/root/repos/scion'
    qparts_repo_url = 'https://github.com/netsys-lab/qparts.git'
    qparts_repo_branch = 'main'
    qparts_repo_path = '/home/root/repos/qparts'


    # SCION ISDs
    base.createIsolationDomain(1)

    # Internet Exchange
    base.createInternetExchange(100, create_rs=False)

    # AS-150
    as150 = base.createAutonomousSystem(150)
    scion_isd.addIsdAs(1, 150, is_core=True)
    as150.createNetwork('net0')
    as150_cs1 = as150.createControlService('cs1').joinNetwork('net0')
    as150_router = as150.createRealWorldRouter('br0', prefixes=['0.0.0.0/1', '128.0.0.0/1'])
    # expectation: hosts from within AS150 can ping outside world i.e. 8.8.8.8
    #   Hosts in the other ASes can't!!
    as150_router.joinNetwork('net0').joinNetwork('ix100')
    as150_router.crossConnect(153, 'br0', '10.50.0.2/29')
    #host150 = as150.createHost('qparts_').joinNetwork('net0', address='10.150.0.40')
    #emu.addBinding(Binding(f'qparts_150', filter=Filter(nodeName=as150_cs1.getName(), asn=150)))
    #svc = devsvc.install(f'qparts_150')
    #svc.checkoutRepo(qparts_repo_url, qparts_repo_path, qparts_repo_branch, AccessMode.shared)
    

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
    as152_cs1 = as152.createControlService('cs1').joinNetwork('net0')
    as152_router = as152.createRealWorldRouter('br0', prefixes=['0.0.0.0/1', '128.0.0.0/1'])
    as152_router.joinNetwork('net0').joinNetwork('ix100')

    # AS-153
    as153 = base.createAutonomousSystem(153)
    scion_isd.addIsdAs(1, 153, is_core=False)
    scion_isd.setCertIssuer((1, 153), issuer=150)
    as153.createNetwork('net0')
    as153_cs1 = as153.createControlService('cs1').joinNetwork('net0')

    as153_router = as153.createRouter('br0')
    as153_router.joinNetwork('net0')
    as153_router.crossConnect(150, 'br0', '10.50.0.3/29')

    # Inter-AS routing
    scion.addIxLink(100, (1, 150), (1, 151), ScLinkType.Core)
    scion.addIxLink(100, (1, 151), (1, 152), ScLinkType.Core)
    scion.addIxLink(100, (1, 152), (1, 150), ScLinkType.Core)
    scion.addXcLink((1, 150), (1, 153), ScLinkType.Transit)

    # BUG: As soon as AS152 gets a real world router, this makes the emulation fail
    #Traceback (most recent call last):
    #    File "/home/marten/sapex-f/seed-emulator/examples/scion/S12_qparts/qparts.py", line 140, in <module>
    #        run()
    #    File "/home/marten/sapex-f/seed-emulator/examples/scion/S12_qparts/qparts.py", line 132, in run
    #        emu.render()
    #    File "/home/marten/sapex-f/seed-emulator/seedemu/core/Emulator.py", line 402, in render
    #        self.__render(layerName, False, False)
    #    File "/home/marten/sapex-f/seed-emulator/seedemu/core/Emulator.py", line 163, in __render
    #        layer.render(self)
    #    File "/home/marten/sapex-f/seed-emulator/seedemu/layers/ScionRouting.py", line 463, in render
    #        super().render(emulator)
    #    File "/home/marten/sapex-f/seed-emulator/seedemu/layers/Routing.py", line 173, in render
    #        r = promote_to_real_world_router(r, False)
    #    File "/home/marten/sapex-f/seed-emulator/seedemu/core/Node.py", line 1345, in promote_to_real_world_router
    #        extn.initRealWorld(hideHops)
    #    File "/home/marten/sapex-f/seed-emulator/seedemu/core/Node.py", line 1240, in initRealWorld
    #        self.get_node().addSoftware('iptables')
    #    AttributeError: 'NoneType' object has no attribute 'addSoftware'

    svc = devsvc.install(f'dev_152_cs1')
    emu.addBinding(Binding(f'dev_152_cs1', filter=Filter(nodeName=as152_cs1.getName(), asn=152)))
    svc.checkoutRepo(repo_url, repo_path, repo_branch, AccessMode.shared)
    # svc.checkoutRepo(qparts_repo_url, qparts_repo_path, qparts_repo_branch, AccessMode.shared)

    svc3 = devsvc.install(f'dev_153_cs1')
    svc3.checkoutRepo(repo_url, repo_path, repo_branch, AccessMode.shared)
    emu.addBinding(Binding(f'dev_153_cs1', filter=Filter(nodeName=as153_cs1.getName(), asn=153)))

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