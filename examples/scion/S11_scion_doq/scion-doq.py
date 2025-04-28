#!/usr/bin/env python3
# encoding: utf-8


from seedemu.services import GolangDevService, AccessMode, DomainNameService
from dataclasses import dataclass
from typing import List
from seedemu.core import Emulator, Binding, Filter, Node, OptionRegistry
from seedemu.layers import (
    ScionBase, ScionRouting, ScionIsd, Scion, SetupSpecification, CheckoutSpecification)
from seedemu.layers import ScionBase, ScionRouting, ScionIsd, Scion
from seedemu.layers.Scion import LinkType as ScLinkType
from seedemu.compiler import Docker, Platform, Graphviz
import os, sys
from ipaddress import IPv4Network
from collections import defaultdict



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



    @dataclass
    class GitRepo:
        repo_url: str
        repo_branch: str
        repo_path: str
        notes: str

    devsvc = GolangDevService( 'amdfxlucas', 'saculolissat@gmx.de' )
    repos = [
             GitRepo( repo_url = 'https://github.com/netsys-lab/ngi-search',
                    repo_branch = 'main',
                    repo_path = '/repos/ngi-search',
                    notes='actually only a README and git-submodule pointers' \
                            'to scion-apps(containing skip), pan-lua and scion-browser-extensions'),

            GitRepo( repo_url = 'https://github.com/netsys-lab/pan-lua',
                    repo_branch = 'main',
                    repo_path = '/repos/pan-lua' ),
            GitRepo( repo_url = 'https://github.com/netsys-lab/panapi',
                    repo_branch = 'main',
                    repo_path = '/repos/panapi' ),

             GitRepo( repo_url = 'https://github.com/netsys-lab/scion-sdns',
                    repo_branch = 'scion',
                    repo_path = '/repos/scion-sdns',
                    notes= 'the recursive resolver that must run on the host \
                            instead of the default systemd-resolved.service ' ),


            GitRepo( repo_url = 'https://github.com/netsys-lab/scion-coredns-doq',
                    repo_branch = 'main',
                    repo_path = '/repos/scion-coredns-doq',
                    notes='SCION DoQ capable coredns nameserver fork based on caddy'
                    # or:  https://github.com/amdfxlucas/scion-coredns branch: impl_doq
                      ),

            GitRepo( repo_url = 'https://github.com/netsys-lab/scion-apps',
                    repo_branch = 'master',
                    repo_path = '/repos/netsys-scion-apps' ),

            GitRepo( repo_url = 'https://github.com/netsys-lab/scion-apps',
                    repo_branch = 'master',
                    repo_path = '/repos/luki-scion-apps' ),

            GitRepo( repo_url = 'https://github.com/netsys-lab/exdns',
                    notes='dig like CLI program for issuing test request to the resolver or NS',
                    repo_branch = 'master',
                    repo_path = '/repos/exdns' ),
            GitRepo( repo_url = 'https://github.com/netsys-lab/dns',
                    repo_branch = 'master',
                    repo_path = '/repos/dns' ),
            GitRepo( repo_url = 'https://github.com/amdfxlucas/dnslookup',
                    repo_branch = 'master',
                    repo_path = '/repos/dnslookup',
                    notes='also CLI dns query tool' ),

            GitRepo(repo_url = 'https://github.com/scionproto-contrib/http-proxy.git',
                    repo_branch = 'main',
                    repo_path = '/repos/http-proxy',
                    notes='a caddy server module for SCION HTTP-proxy functionality' ),


            GitRepo(repo_url = 'https://github.com/scionproto-contrib/caddy-scion',
                    repo_branch = 'main',
                    repo_path = '/repos/caddy-scion',
                    notes='caddy server plugins' ),

            GitRepo(repo_url = 'https://github.com/netsys-lab/scion-rdig',
                    repo_branch = 'main',
                    repo_path = '/repos/scion-rdig',
                    notes='dig like CLI tool for dns queries that supports RHINE' )




            ]
    def install_dev_svc(emu: Emulator, node: Node, devsvc, repos: List[GitRepo] ):

        vnodename = f'dev_{node.getAsn()}_{node.getName()}'
        svc = devsvc.install(vnodename)

        for r in repos:

            svc.checkoutRepo(r.repo_url,r.repo_path, r.repo_branch, AccessMode.shared)
        emu.addBinding(Binding(vnodename,
                               filter=Filter(nodeName=node.getName(),
                                             asn=node.getAsn())))

    ases = {}
    brs = defaultdict()
    cses = defaultdict()

    dns_svc = DomainNameService()

    def create_as(isd, asn, is_core=False, issuer=None):
        as_ = base.createAutonomousSystem(asn)
        scion_isd.addIsdAs(isd, asn, is_core)
        if not is_core:
            scion_isd.setCertIssuer((isd, asn), issuer)
        as_.createNetwork('net0')
        _cs = as_.createControlService('cs1').joinNetwork('net0')
        as_.setBeaconingIntervals('60s', '60s', '60s')
        if is_core:
            # 'MaxHopsLength': 4,
            policy = {
                'Filter': {
                    'AllowIsdLoop': False
                }
            }
            as_.setBeaconPolicy('propagation', policy)
            as_.setBeaconPolicy('core_registration', policy)
        else:
            '''
            used by a non-core AS to determine which down-segments it wants to make available to other ASes.
            Each selected down-segments is registered, via a segment registration request,
            in the core AS that originated it.
            '''
            down_policy = {
                'Filter': {}
            }
            as_.setBeaconPolicy('down_registration', down_policy)

        br = as_.createRouter('br0')
        br.joinNetwork('net0')

        ia = f'{isd}-{asn}'
        ases[ia] = as_
        brs[ia] = br
        cses[ia] = _cs

        return as_, br


    class CrossConnectNetAssigner:
        def __init__(self):
            self.subnet_iter = IPv4Network("10.3.0.0/16").subnets(new_prefix=29)
            self.xc_nets = {}

        def next_addr(self, net):
            if net not in self.xc_nets:
                hosts = next(self.subnet_iter).hosts()
                next(hosts) # Skip first IP (reserved for Docker)
                self.xc_nets[net] = hosts
            return "{}/29".format(next(self.xc_nets[net]))

    xc_nets = CrossConnectNetAssigner()


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
    routing = ScionRouting()
    scion_isd = ScionIsd()
    scion = Scion()

    # SCION ISDs
    base.createIsolationDomain(1)
    base.createIsolationDomain(2)

    # core AS ISD 1
    create_as(1, 150, is_core=True)
    create_as(1, 151, is_core=True)
    create_as(1, 152, is_core=True)
    # core AS ISD 2
    create_as(2, 240, is_core=True)
    create_as(2, 241, is_core=True)
    create_as(2, 242, is_core=True)

    # non-core AS ISD1
    create_as(1, 171, issuer=151)
    create_as(1, 170, issuer=152)
    create_as(1, 172, issuer=151)
    create_as(1, 173, issuer=151)
    create_as(1, 174, issuer=151)
    # non-core AS ISD2
    create_as(2, 230, issuer=241)
    create_as(2, 231, issuer=241)
    create_as(2, 232, issuer=241)
    create_as(2, 235, issuer=241)
    create_as(2, 236, issuer=241)
    create_as(2, 233, issuer=242)
    create_as(2, 234, issuer=242)


    # Aliased AS
    #create_as(1, 101, issuer=151)# site 1
    create_as(1, 102, issuer=152)# site 2
    create_as(2, 203, issuer=241)# site 3
    #create_as(2, 204, issuer=241)# site 4
    #create_as(2, 205, issuer=151)# site 5

    # connect site2 to its provider 1-174
    brs['1-102'].crossConnect(174, 'br0', xc_nets.next_addr('102-174'))
    brs['1-174'].crossConnect(102, 'br0', xc_nets.next_addr('102-174'))
    scion.addXcLink((1, 174), (1, 102), ScLinkType.Transit)

    # connect site3 to its provider 2-236
    brs['2-203'].crossConnect(236, 'br0', xc_nets.next_addr('203-236'))
    brs['2-236'].crossConnect(203, 'br0', xc_nets.next_addr('203-236'))
    scion.addXcLink((2, 236), (2, 203), ScLinkType.Transit)


    # core links of ISD1
    brs['1-150'].crossConnect(151, 'br0', xc_nets.next_addr('150-151'))
    brs['1-151'].crossConnect(150, 'br0', xc_nets.next_addr('150-151'))
    brs['1-150'].crossConnect(152, 'br0', xc_nets.next_addr('150-152'))
    brs['1-152'].crossConnect(150, 'br0', xc_nets.next_addr('150-152'))
    brs['1-151'].crossConnect(152, 'br0', xc_nets.next_addr('151-152'))
    brs['1-152'].crossConnect(151, 'br0', xc_nets.next_addr('151-152'))
    scion.addXcLink((1, 150), (1, 151), ScLinkType.Core, count=2)
    scion.addXcLink((1, 151), (1, 152), ScLinkType.Core, count=2)
    scion.addXcLink((1, 150), (1, 152), ScLinkType.Core, count=2)


    # core links of ISD2
    brs['2-240'].crossConnect(241, 'br0', xc_nets.next_addr('240-241'))
    brs['2-241'].crossConnect(240, 'br0', xc_nets.next_addr('240-241'))
    brs['2-240'].crossConnect(242, 'br0', xc_nets.next_addr('240-242'))
    brs['2-242'].crossConnect(240, 'br0', xc_nets.next_addr('240-242'))
    brs['2-241'].crossConnect(242, 'br0', xc_nets.next_addr('241-242'))
    brs['2-242'].crossConnect(241, 'br0', xc_nets.next_addr('241-242'))
    scion.addXcLink((2, 240), (2, 241), ScLinkType.Core, count=2)
    scion.addXcLink((2, 240), (2, 242), ScLinkType.Core, count=2)
    scion.addXcLink((2, 241), (2, 242), ScLinkType.Core, count=2)

    # inter ISD links
    brs['2-240'].crossConnect(150, 'br0', xc_nets.next_addr('150-240'))
    brs['1-150'].crossConnect(240, 'br0', xc_nets.next_addr('150-240'))
    brs['2-241'].crossConnect(152, 'br0', xc_nets.next_addr('152-241'))
    brs['1-152'].crossConnect(241, 'br0', xc_nets.next_addr('152-241'))
    scion.addXcLink((1, 150), (2, 240), ScLinkType.Core, count=2)
    scion.addXcLink((1, 152), (2, 241), ScLinkType.Core, count=2)

    # transit links ISD1
    brs['1-151'].crossConnect(171, 'br0', xc_nets.next_addr('151-171'))
    brs['1-171'].crossConnect(151, 'br0', xc_nets.next_addr('151-171'))
    brs['1-171'].crossConnect(172, 'br0', xc_nets.next_addr('171-172'))
    brs['1-172'].crossConnect(171, 'br0', xc_nets.next_addr('171-172'))
    brs['1-151'].crossConnect(170, 'br0', xc_nets.next_addr('151-170'))
    brs['1-170'].crossConnect(151, 'br0', xc_nets.next_addr('151-170'))
    brs['1-152'].crossConnect(170, 'br0', xc_nets.next_addr('152-170'))
    brs['1-170'].crossConnect(152, 'br0', xc_nets.next_addr('152-170'))
    brs['1-170'].crossConnect(174, 'br0', xc_nets.next_addr('170-174'))
    brs['1-174'].crossConnect(170, 'br0', xc_nets.next_addr('170-174'))
    brs['1-170'].crossConnect(173, 'br0', xc_nets.next_addr('170-173'))
    brs['1-173'].crossConnect(170, 'br0', xc_nets.next_addr('170-173'))
    scion.addXcLink((1, 151), (1, 171), ScLinkType.Transit)
    scion.addXcLink((1, 171), (1, 172), ScLinkType.Transit)
    scion.addXcLink((1, 151), (1, 170), ScLinkType.Transit)
    scion.addXcLink((1, 152), (1, 170), ScLinkType.Transit)
    scion.addXcLink((1, 170), (1, 174), ScLinkType.Transit)
    scion.addXcLink((1, 170), (1, 173), ScLinkType.Transit)

    # transit links ISD2
    brs['2-241'].crossConnect(230, 'br0', xc_nets.next_addr('241-230'))
    brs['2-230'].crossConnect(241, 'br0', xc_nets.next_addr('241-230'))
    brs['2-241'].crossConnect(232, 'br0', xc_nets.next_addr('241-232'))
    brs['2-232'].crossConnect(241, 'br0', xc_nets.next_addr('241-232'))
    brs['2-242'].crossConnect(233, 'br0', xc_nets.next_addr('242-233'))
    brs['2-233'].crossConnect(242, 'br0', xc_nets.next_addr('242-233'))
    brs['2-230'].crossConnect(231, 'br0', xc_nets.next_addr('230-231'))
    brs['2-231'].crossConnect(230, 'br0', xc_nets.next_addr('230-231'))
    brs['2-230'].crossConnect(236, 'br0', xc_nets.next_addr('230-236'))
    brs['2-236'].crossConnect(230, 'br0', xc_nets.next_addr('230-236'))
    brs['2-232'].crossConnect(235, 'br0', xc_nets.next_addr('232-235'))
    brs['2-235'].crossConnect(232, 'br0', xc_nets.next_addr('232-235'))
    brs['2-233'].crossConnect(234, 'br0', xc_nets.next_addr('233-234'))
    brs['2-234'].crossConnect(233, 'br0', xc_nets.next_addr('233-234'))
    scion.addXcLink((2, 241), (2, 230), ScLinkType.Transit)
    scion.addXcLink((2, 241), (2, 232), ScLinkType.Transit)
    scion.addXcLink((2, 242), (2, 233), ScLinkType.Transit)
    scion.addXcLink((2, 230), (2, 231), ScLinkType.Transit)
    scion.addXcLink((2, 230), (2, 236), ScLinkType.Transit)
    scion.addXcLink((2, 232), (2, 235), ScLinkType.Transit)
    scion.addXcLink((2, 233), (2, 234), ScLinkType.Transit)

    # perring links
    brs['2-232'].crossConnect(233, 'br0', xc_nets.next_addr('232-233'))
    brs['2-233'].crossConnect(232, 'br0', xc_nets.next_addr('232-233'))
    scion.addXcLink((2, 232), (2, 233), ScLinkType.Peer)
    brs['2-230'].crossConnect(232, 'br0', xc_nets.next_addr('230-232'))
    brs['2-232'].crossConnect(230, 'br0', xc_nets.next_addr('230-232'))
    scion.addXcLink((2, 230), (2, 232), ScLinkType.Peer)
    brs['1-171'].crossConnect(170, 'br0', xc_nets.next_addr('170-171'))
    brs['1-170'].crossConnect(171, 'br0', xc_nets.next_addr('170-171'))
    scion.addXcLink((1, 170), (1, 171), ScLinkType.Peer)
    brs['1-170'].crossConnect(230, 'br0', xc_nets.next_addr('170-230'))
    brs['2-230'].crossConnect(170, 'br0', xc_nets.next_addr('170-230'))
    scion.addXcLink((1, 170), (2, 230), ScLinkType.Peer)


    from seedemu.utilities import createHostsOnNetwork
    # nodes who should have a DevService installed
    dev_targets = []
    client_ases = [102,172, 173, 231, 234, 203, 235]
    for asn in client_ases:
        as_ = base.getAutonomousSystem(asn)
        createHostsOnNetwork(emu, as_, 'net0', [])
        hnode = as_.getHost('host_0')
        dev_targets.append(hnode)

    # HTTP FWD proxy and sdns rec. resolver
    # 'entrypoint' into the simulation for browser-extension
    host_a = base.getAutonomousSystem(102).getHost('host_0')
    host_a.addPortForwarding(8888,8888, 'tcp')

    # HTTP web server and HTTP reverse proxy ...........................

    host_web_1 = base.getAutonomousSystem(172).getHost('host_0')

    host_web_2 = base.getAutonomousSystem(173).getHost('host_0')


    # coredns DoQ nameservers ..........................................
    # root '.'
    host_ns_1 = base.getAutonomousSystem(235).getHost('host_0')

    # 'com.' zone
    host_ns_2 = base.getAutonomousSystem(234).getHost('host_0')

    # 'net.'
    host_ns_3 = base.getAutonomousSystem(203).getHost('host_0')

    # 'edu.'
    host_ns_4 = base.getAutonomousSystem(231).getHost('host_0')

    for node in dev_targets:
        install_dev_svc(emu, node, devsvc, repos )


    # Rendering
    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(scion_isd)
    emu.addLayer(scion)
    emu.addLayer(dns_svc)
    emu.addLayer(devsvc)




    if dumpfile is not None:
        emu.dump(dumpfile)
    else:
        emu.render()

        ###############################################################################
        # Compilation

        emu.compile(Docker(platform=platform), './output', override=True)
        #emu.compile(Graphviz(), './output_graph', override=True)

if __name__ == "__main__":
    run()