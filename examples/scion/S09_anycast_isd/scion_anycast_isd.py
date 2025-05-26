#!/usr/bin/env python3
# encoding: utf-8


from seedemu.services import GolangDevService, AccessMode
from dataclasses import dataclass
from typing import List
from seedemu.core import Emulator,OptionRegistry, Binding, Filter, Node
from seedemu.layers import (
    ScionBase, ScionRouting, ScionIsd, Scion, SetupSpecification, CheckoutSpecification)
from seedemu.layers import ScionBase, ScionRouting, ScionIsd, Scion
from seedemu.layers.Scion import LinkType as ScLinkType
from seedemu.compiler import Docker, Platform
import os, sys
from ipaddress import IPv4Network



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

    # your git credentials go here
    devsvc = GolangDevService( 'johndoe', 'john.doe@gmx.de' )
    # your repo ...
    repo = GitRepo( repo_url = 'https://github.com/johndoe/scion',
                    repo_branch = 'feature-dev',
                    repo_path = '/home/root/repos/scion' )
    def install_dev_svc(emu: Emulator, node: Node, devsvc, repos: List[GitRepo] ):

        vnodename = f'dev_{node.getAsn()}_{node.getName()}'
        svc = devsvc.install(vnodename)

        for r in repos:

            svc.checkoutRepo(r.repo_url,r.repo_path, r.repo_branch, AccessMode.shared)
        emu.addBinding(Binding(vnodename,
                               filter=Filter(nodeName=node.getName(),
                                             asn=node.getAsn())))


    def create_as(isd, asn, is_core=False, issuer=None):
        as_ = base.createAutonomousSystem(asn)
        scion_isd.addIsdAs(isd, asn, is_core)
        if not is_core:
            scion_isd.setCertIssuer((isd, asn), issuer)
        as_.createNetwork('net0')
        as_.createControlService('cs1').joinNetwork('net0')
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
        else: # client AS
            '''
            used by a non-core AS to determine which down-segments it wants to make available to other ASes.
            Each selected down-segments is registered, via a segment registration request,
            in the core AS that originated it.
            '''
            # Deny-list for ASes. PCBs with any AS entry from any
            #  of the specified AS identifiers will be rejected. (not registered as DOWN seg)
            down_policy = {
                'Filter': { 'AsBlackList': [222]}
            }
            # alternatively: 'IsdBlackList' for AnycastISD
            as_.setBeaconPolicy('down_registration', down_policy)

        br = as_.createRouter('br0')
        br.joinNetwork('net0')
        return as_, br

    def create_anycast(isd, asn):
        """
        the anycast ISD contains only core ASes,
        which do not propagate core beacons but only originate them.
        """
        as_ = base.createAutonomousSystem(asn)
        scion_isd.addIsdAs(isd, asn, True)

        as_.createNetwork('net0')
        as_.createControlService('cs1').joinNetwork('net0')
        as_.setBeaconingIntervals('60s', '1y', '60s')
        #  determines which beacons are selected to be propagated and how they are extended.
        # in short: -> don't propagate anything at all !!
        prop_policy = {
            'Filter': {
                'IsdBlackList': [1],
                'AllowIsdLoop': True
            }   }

        as_.setBeaconPolicy('propagation', prop_policy)
        #as_.setBeaconPolicy('core_registration', core_policy)
        br = as_.createRouter('br0')
        br.joinNetwork('net0')
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
    base.createIsolationDomain(2) # Anycast ISD

    # Internet Exchanges
    # We use "Internet Exchanges" as internal networks of the subdivided ASes in
    # order to reduce the number of networks Docker has to create.
    base.createInternetExchange(5, create_rs=False)  # Tier-1 ISP
    base.createInternetExchange(7, create_rs=False)  # Tier-1 ISP
    base.createInternetExchange(10, create_rs=False) # Large IXP
    base.createInternetExchange(11, create_rs=False) # Large IXP
    base.createInternetExchange(12, create_rs=False) # Small IXP
    base.createInternetExchange(17, create_rs=False) # Small access network
    base.createInternetExchange(18, create_rs=False) # Large access network
    base.createInternetExchange(20, create_rs=False) # Large content provider

    # Tier-1 ISP as50-53
    br = create_as(1, 50, is_core=True)[1].joinNetwork('ix5')
    br.crossConnect(222, 'br0', xc_nets.next_addr('50-222')) # b
    br.crossConnect(60, 'br0', xc_nets.next_addr('50-60'))
    br.crossConnect(70, 'br0', xc_nets.next_addr('50-70'))
    br.crossConnect(201, 'br0', xc_nets.next_addr('50-201'))
    br = create_as(1, 51, issuer=50)[1].joinNetwork('ix5')
    br.crossConnect(150, 'br0', xc_nets.next_addr('51-150'))
    br.crossConnect(151, 'br0', xc_nets.next_addr('51-151'))
    br.crossConnect(181, 'br0', xc_nets.next_addr('51-181'))
    create_as(1, 52, issuer=50)[1].joinNetwork('ix5')
    br = create_as(1, 53, issuer=50)[1].joinNetwork('ix5')
    br.crossConnect(152, 'br0', xc_nets.next_addr('53-152'))
    scion.addIxLink(5, (1, 50), (1, 51), ScLinkType.Transit)
    scion.addIxLink(5, (1, 50), (1, 52), ScLinkType.Transit)
    scion.addIxLink(5, (1, 50), (1, 53), ScLinkType.Transit)
    scion.addIxLink(5, (1, 52), (1, 51), ScLinkType.Transit, count=2)
    scion.addIxLink(5, (1, 52), (1, 53), ScLinkType.Transit, count=2)

    # Tier-1 ISP as60
    _, br = create_as(1, 60, is_core=True)
    br.crossConnect(222, 'br0', xc_nets.next_addr('60-222')) # c
    br.crossConnect(50, 'br0', xc_nets.next_addr('50-60'))
    br.crossConnect(70, 'br0', xc_nets.next_addr('60-70'))
    br.crossConnect(103, 'br0', xc_nets.next_addr('60-103'))
    br.crossConnect(152, 'br0', xc_nets.next_addr('60-152'))
    br.crossConnect(180, 'br0', xc_nets.next_addr('60-180'))

    # Tier-1 ISP as70-73
    br = create_as(1, 70, is_core=True)[1].joinNetwork('ix7')
    br.crossConnect(222, 'br0', xc_nets.next_addr('70-222')) # a
    br.crossConnect(50, 'br0', xc_nets.next_addr('50-70'))
    br.crossConnect(60, 'br0', xc_nets.next_addr('60-70'))
    br.crossConnect(110, 'br0', xc_nets.next_addr('70-110'))
    br.crossConnect(170, 'br0', xc_nets.next_addr('70-170'))
    br.crossConnect(200, 'br0', xc_nets.next_addr('70-200'))
    br = create_as(1, 71, issuer=70)[1].joinNetwork('ix7')
    br.crossConnect(120, 'br0', xc_nets.next_addr('71-120'))
    br.crossConnect(160, 'br0', xc_nets.next_addr('71-160'))
    br.crossConnect(161, 'br0', xc_nets.next_addr('71-161'))
    create_as(1, 72, issuer=70)[1].joinNetwork('ix7')
    br = create_as(1, 73, issuer=70)[1].joinNetwork('ix7')
    br.crossConnect(162, 'br0', xc_nets.next_addr('73-162'))
    br.crossConnect(163, 'br0', xc_nets.next_addr('73-163'))
    scion.addIxLink(7, (1, 70), (1, 71), ScLinkType.Transit)
    scion.addIxLink(7, (1, 70), (1, 72), ScLinkType.Transit)
    scion.addIxLink(7, (1, 70), (1, 73), ScLinkType.Transit)
    scion.addIxLink(7, (1, 72), (1, 71), ScLinkType.Transit, count=2)
    scion.addIxLink(7, (1, 72), (1, 73), ScLinkType.Transit, count=2)

    # Anycast AS
    any_as, any_br = create_anycast(2, 222)
    any_br.crossConnect(70, 'br0', xc_nets.next_addr('70-222')) # a
    any_br.crossConnect(50, 'br0', xc_nets.next_addr('50-222')) # b
    any_br.crossConnect(60, 'br0', xc_nets.next_addr('60-222')) # c
    '''
    br.crossConnect(110, 'br0', xc_nets.next_addr('110-222')) # d
    br.crossConnect(111, 'br0', xc_nets.next_addr('111-222')) # e
    br.crossConnect(100, 'br0', xc_nets.next_addr('100-222')) # g
    br.crossConnect(101, 'br0', xc_nets.next_addr('101-222')) # f
    br.crossConnect(102, 'br0', xc_nets.next_addr('102-222')) # i
    br.crossConnect(103, 'br0', xc_nets.next_addr('103-222')) # h
    '''


    # Large IXP as100-113
    br = create_as(1, 100, is_core=True)[1].joinNetwork('ix10')
    br.crossConnect(111, 'br0', xc_nets.next_addr('100-111'))
    create_as(1, 101, is_core=True)[1].joinNetwork('ix10')
    create_as(1, 102, is_core=True)[1].joinNetwork('ix10')
    br = create_as(1, 103, is_core=True)[1].joinNetwork('ix10')
    br.crossConnect(60, 'br0', xc_nets.next_addr('60-103'))
    create_as(1, 104, issuer=100)[1].joinNetwork('ix10')
    create_as(1, 105, issuer=100)[1].joinNetwork('ix10')
    create_as(1, 106, issuer=100)[1].joinNetwork('ix10')
    create_as(1, 107, issuer=100)[1].joinNetwork('ix10')
    create_as(1, 108, issuer=100)[1].joinNetwork('ix10')
    create_as(1, 109, issuer=100)[1].joinNetwork('ix10')
    scion.addIxLink(10, (1, 100), (1, 101), ScLinkType.Core)
    scion.addIxLink(10, (1, 101), (1, 102), ScLinkType.Core)
    scion.addIxLink(10, (1, 102), (1, 103), ScLinkType.Core)
    scion.addIxLink(10, (1, 100), (1, 102), ScLinkType.Core)
    scion.addIxLink(10, (1, 101), (1, 103), ScLinkType.Core)
    scion.addIxLink(10, (1, 100), (1, 104), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 100), (1, 105), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 100), (1, 106), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 100), (1, 107), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 101), (1, 104), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 101), (1, 105), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 101), (1, 106), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 101), (1, 107), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 102), (1, 104), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 102), (1, 105), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 102), (1, 106), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 102), (1, 107), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 103), (1, 104), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 103), (1, 105), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 103), (1, 106), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 103), (1, 107), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 105), (1, 108), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 106), (1, 109), ScLinkType.Transit, count=2)
    br = create_as(1, 110, is_core=True)[1].joinNetwork('ix11')
    br.crossConnect(70, 'br0', xc_nets.next_addr('70-110'))
    br = create_as(1, 111, is_core=True)[1].joinNetwork('ix11')
    br.crossConnect(100, 'br0', xc_nets.next_addr('100-111'))
    create_as(1, 112, issuer=110)[1].joinNetwork('ix11')
    create_as(1, 113, issuer=110)[1].joinNetwork('ix11')
    scion.addIxLink(11, (1, 110), (1, 111), ScLinkType.Core)
    scion.addIxLink(11, (1, 110), (1, 112), ScLinkType.Transit, count=2)
    scion.addIxLink(11, (1, 110), (1, 113), ScLinkType.Transit, count=2)
    scion.addIxLink(11, (1, 111), (1, 112), ScLinkType.Transit, count=2)
    scion.addIxLink(11, (1, 111), (1, 113), ScLinkType.Transit, count=2)

    # Small IXP as120-122
    br = create_as(1, 120, is_core=True)[1].joinNetwork('ix12')
    br.crossConnect(71, 'br0', xc_nets.next_addr('71-120'))
    create_as(1, 121, issuer=120)[1].joinNetwork('ix12')
    create_as(1, 122, issuer=120)[1].joinNetwork('ix12')
    scion.addIxLink(12, (1, 120), (1, 121), ScLinkType.Transit, count=2)
    scion.addIxLink(12, (1, 120), (1, 122), ScLinkType.Transit, count=2)

    # Large content provider as200-205
    br = create_as(1, 200, is_core=True)[1].joinNetwork('ix20')
    br.crossConnect(70, 'br0', xc_nets.next_addr('70-200'))
    br = create_as(1, 201, is_core=True)[1].joinNetwork('ix20')
    br.crossConnect(50, 'br0', xc_nets.next_addr('50-201'))
    create_as(1, 202, issuer=200)[1].joinNetwork('ix20').joinNetwork('ix11').joinNetwork('ix12')
    create_as(1, 203, issuer=200)[1].joinNetwork('ix20').joinNetwork('ix10')
    br = create_as(1, 204, issuer=200)[1].joinNetwork('ix20')
    br.crossConnect(163, 'br0', xc_nets.next_addr('163-204'))
    br = create_as(1, 205, issuer=200)[1].joinNetwork('ix20')
    br.crossConnect(150, 'br0', xc_nets.next_addr('150-205'))
    scion.addIxLink(20, (1, 200), (1, 201), ScLinkType.Core, count=2)
    scion.addIxLink(20, (1, 200), (1, 202), ScLinkType.Transit)
    scion.addIxLink(20, (1, 202), (1, 204), ScLinkType.Transit)
    scion.addIxLink(20, (1, 201), (1, 203), ScLinkType.Transit)
    scion.addIxLink(20, (1, 203), (1, 205), ScLinkType.Transit)
    scion.addIxLink(11, (1, 113), (1, 202), ScLinkType.Transit, count=2)
    scion.addIxLink(10, (1, 104), (1, 203), ScLinkType.Transit, count=2)
    scion.addIxLink(12, (1, 122), (1, 202), ScLinkType.Transit)

    # Small access network as170-171
    br = create_as(1, 170, is_core=True)[1].joinNetwork('ix17')
    br.crossConnect(70, 'br0', xc_nets.next_addr('70-170'))
    create_as(1, 171, issuer=170)[1].joinNetwork('ix17').joinNetwork('ix11').joinNetwork('ix12')
    scion.addIxLink(17, (1, 170), (1, 171), ScLinkType.Transit)
    scion.addIxLink(11, (1, 112), (1, 171), ScLinkType.Transit, count=2)
    scion.addIxLink(12, (1, 121), (1, 171), ScLinkType.Transit)

    # Core links
    scion.addXcLink((1, 50), (1, 60), ScLinkType.Core)
    scion.addXcLink((1, 50), (1, 70), ScLinkType.Core, count=2)
    scion.addXcLink((1, 60), (1, 70), ScLinkType.Core)
    scion.addXcLink((1, 50), (1, 201), ScLinkType.Core)
    scion.addXcLink((1, 60), (1, 103), ScLinkType.Core)
    scion.addXcLink((1, 70), (1, 200), ScLinkType.Core)
    scion.addXcLink((1, 70), (1, 110), ScLinkType.Core)
    scion.addXcLink((1, 70), (1, 170), ScLinkType.Core)
    scion.addXcLink((1, 100), (1, 111), ScLinkType.Core)

    # Core links to Anycast AS
    scion.addXcLink((2, 222), (1, 70), ScLinkType.Core) # a
    scion.addXcLink((2, 222), (1, 50), ScLinkType.Core) # b
    scion.addXcLink((2, 222), (1, 60), ScLinkType.Core) # c
    '''
    scion.addXcLink((1, 222), (1, 110), ScLinkType.Core) # d
    scion.addXcLink((1, 222), (1, 111), ScLinkType.Core) # e
    scion.addXcLink((1, 222), (1, 100), ScLinkType.Core) # g
    scion.addXcLink((1, 222), (1, 101), ScLinkType.Core) # f
    scion.addXcLink((1, 222), (1, 102), ScLinkType.Core) # i
    scion.addXcLink((1, 222), (1, 103), ScLinkType.Core) # h
    '''

    # Large access network as180-191
    br = create_as(1, 180, is_core=True)[1].joinNetwork('ix18')
    br.crossConnect(60, 'br0', xc_nets.next_addr('60-180'))
    br = create_as(1, 181, issuer=180)[1].joinNetwork('ix18').joinNetwork('ix10')
    br.crossConnect(51, 'br0', xc_nets.next_addr('51-181'))
    br = create_as(1, 182, issuer=180)[1].joinNetwork('ix18').joinNetwork('ix10')
    br = create_as(1, 183, issuer=180)[1].joinNetwork('ix18').joinNetwork('ix10')
    for asn in range(184, 192):
        create_as(1, asn, issuer=180)[1].joinNetwork('ix18')
    scion.addIxLink(18, (1, 180), (1, 181), ScLinkType.Transit)
    scion.addIxLink(18, (1, 180), (1, 182), ScLinkType.Transit)
    scion.addIxLink(18, (1, 180), (1, 183), ScLinkType.Transit)
    scion.addIxLink(18, (1, 181), (1, 184), ScLinkType.Transit)
    scion.addIxLink(18, (1, 181), (1, 185), ScLinkType.Transit)
    scion.addIxLink(18, (1, 182), (1, 184), ScLinkType.Transit)
    scion.addIxLink(18, (1, 182), (1, 185), ScLinkType.Transit)
    scion.addIxLink(18, (1, 182), (1, 186), ScLinkType.Transit)
    scion.addIxLink(18, (1, 183), (1, 185), ScLinkType.Transit)
    scion.addIxLink(18, (1, 183), (1, 186), ScLinkType.Transit)
    scion.addIxLink(18, (1, 184), (1, 187), ScLinkType.Transit)
    scion.addIxLink(18, (1, 184), (1, 188), ScLinkType.Transit)
    scion.addIxLink(18, (1, 184), (1, 189), ScLinkType.Transit)
    scion.addIxLink(18, (1, 185), (1, 187), ScLinkType.Transit)
    scion.addIxLink(18, (1, 185), (1, 188), ScLinkType.Transit)
    scion.addIxLink(18, (1, 185), (1, 190), ScLinkType.Transit)
    scion.addIxLink(18, (1, 185), (1, 191), ScLinkType.Transit)
    scion.addIxLink(18, (1, 186), (1, 189), ScLinkType.Transit)
    scion.addIxLink(18, (1, 186), (1, 190), ScLinkType.Transit)
    scion.addIxLink(18, (1, 186), (1, 191), ScLinkType.Transit)
    scion.addXcLink((1, 60), (1, 180), ScLinkType.Core)
    scion.addXcLink((1, 51), (1, 181), ScLinkType.Transit)
    scion.addIxLink(10, (1, 108), (1, 181), ScLinkType.Transit)
    scion.addIxLink(10, (1, 109), (1, 182), ScLinkType.Transit)
    scion.addIxLink(10, (1, 107), (1, 183), ScLinkType.Transit)

    # Leaf ASes
    br = create_as(1, 150, issuer=50)[1].joinNetwork('ix10')
    br.crossConnect(51, 'br0', xc_nets.next_addr('51-150'))
    br.crossConnect(205, 'br0', xc_nets.next_addr('150-205'))
    scion.addXcLink((1, 51), (1, 150), ScLinkType.Transit)
    scion.addIxLink(10, (1, 104), (1, 150), ScLinkType.Transit)
    scion.addXcLink((1, 205), (1, 150), ScLinkType.Transit)

    br = create_as(1, 151, issuer=50)[1].joinNetwork('ix10')
    br.crossConnect(51, 'br0', xc_nets.next_addr('51-151'))
    scion.addXcLink((1, 51), (1, 151), ScLinkType.Transit)
    scion.addIxLink(10, (1, 104), (1, 151), ScLinkType.Transit)
    scion.addIxLink(10, (1, 105), (1, 151), ScLinkType.Transit)

    br = create_as(1, 152, issuer=50)[1].joinNetwork('ix10')
    br.crossConnect(53, 'br0', xc_nets.next_addr('53-152'))
    br.crossConnect(60, 'br0', xc_nets.next_addr('60-152'))
    scion.addXcLink((1, 53), (1, 152), ScLinkType.Transit)
    scion.addXcLink((1, 60), (1, 152), ScLinkType.Transit)
    scion.addIxLink(10, (1, 107), (1, 152), ScLinkType.Transit)

    br = create_as(1, 160, issuer=70)[1].joinNetwork('ix11').joinNetwork('ix12')
    br.crossConnect(71, 'br0', xc_nets.next_addr('71-160'))
    scion.addXcLink((1, 71), (1, 160), ScLinkType.Transit)
    scion.addIxLink(11, (1, 112), (1, 160), ScLinkType.Transit)
    scion.addIxLink(12, (1, 121), (1, 160), ScLinkType.Transit)

    br = create_as(1, 161, issuer=70)[1].joinNetwork('ix12')
    br.crossConnect(71, 'br0', xc_nets.next_addr('71-161'))
    scion.addXcLink((1, 71), (1, 161), ScLinkType.Transit)
    scion.addIxLink(12, (1, 121), (1, 161), ScLinkType.Transit)

    br = create_as(1, 162, issuer=70)[1].joinNetwork('ix12')
    br.crossConnect(73, 'br0', xc_nets.next_addr('73-162'))
    scion.addXcLink((1, 73), (1, 162), ScLinkType.Transit)
    scion.addIxLink(12, (1, 122), (1, 162), ScLinkType.Transit)

    br = create_as(1, 163, issuer=70)[1].joinNetwork('ix11').joinNetwork('ix12')
    br.crossConnect(73, 'br0', xc_nets.next_addr('73-163'))
    br.crossConnect(204, 'br0', xc_nets.next_addr('163-204'))
    scion.addXcLink((1, 73), (1, 163), ScLinkType.Transit)
    scion.addXcLink((1, 204), (1, 163), ScLinkType.Transit)
    scion.addIxLink(11, (1, 113), (1, 163), ScLinkType.Transit)
    scion.addIxLink(12, (1, 122), (1, 163), ScLinkType.Transit)

    # comment out, if you don't want to do development in the simulator
    from seedemu.utilities import createHostsOnNetwork
    client_ases = [ 150, 151, 152,
                   160, 161, 162, 163,
                   170, 171,
                   180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191]
    for asn in client_ases:
        as_ = base.getAutonomousSystem(asn)
        createHostsOnNetwork(emu, as_, 'net0', [])
        hnode = as_.getHost('host_0')
        install_dev_svc(emu, hnode, devsvc, [repo] )


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