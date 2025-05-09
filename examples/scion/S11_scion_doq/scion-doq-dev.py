#!/usr/bin/env python3
# encoding: utf-8


from seedemu.services import (GolangDevService, AccessMode,
                              DomainNameService, DomainNameServer, WebService, WebServerKind,
                              MiniCAService, RootMiniCAStore, MiniCAServer,
                              DomainNameCachingService, DomainNameCachingServer)
from seedemu.services.dns.DNSCommon import *
from dataclasses import dataclass
from typing import List
from seedemu.core import Emulator, Binding, Filter, Node, OptionRegistry
from seedemu.layers import (
    ScionBase, ScionRouting, ScionIsd, Scion, SetupSpecification, CheckoutSpecification, EtcHosts)
from seedemu.layers import ScionBase, ScionRouting, ScionIsd, Scion
from seedemu.layers.Scion import LinkType as ScLinkType
from seedemu.compiler import Docker, Platform, Graphviz
import os, sys
from ipaddress import IPv4Network
from collections import defaultdict

WebSiteContents = {}
WebSiteContents['index_template'] = '''\
<h1> {asn}-{nodeName} {domain} {address}</h1>
<pre>
{body}
</pre>
'''

WebSiteContents['www_example_com'] ='''\
                                                                                 ___
                                                                                /\_ \ 
 __  __  __  __  __  __  __  __  __        __   __  _    __      ___ ___   _____\//\ \      __        ___    ___     ___ ___
/\ \/\ \/\ \/\ \/\ \/\ \/\ \/\ \/\ \     /'__`\/\ \/'\ /'__`\  /' __` __`\/\ '__`\\\\ \ \   /'__`\     /'___\ / __`\ /' __` __`\ 
\ \ \_/ \_/ \ \ \_/ \_/ \ \ \_/ \_/ \ __/\  __/\/>  <//\ \L\.\_/\ \/\ \/\ \ \ \L\ \\\\_\ \_/\  __/  __/\ \__//\ \L\ \/\ \/\ \/\ \ 
 \ \___x___/'\ \___x___/'\ \___x___/'/\_\ \____\/\_/\_\ \__/.\_\ \_\ \_\ \_\ \ ,__//\____\ \____\/\_\ \____\ \____/\ \_\ \_\ \_\ 
  \/__//__/   \/__//__/   \/__//__/  \/_/\/____/\//\/_/\/__/\/_/\/_/\/_/\/_/\ \ \/ \/____/\/____/\/_/\/____/\/___/  \/_/\/_/\/_/
                                                                             \ \_\ 
                                                                              \/_/
'''

WebSiteContents['www_example_net'] = '''\
                                                                                       888                          888
                                                                                       888                          888
                                                                                       888                          888
888  888  888888  888  888888  888  888    .d88b. 888  888 8888b. 88888b.d88b. 88888b. 888 .d88b.   88888b.  .d88b. 888888
888  888  888888  888  888888  888  888   d8P  Y8b`Y8bd8P'    "88b888 "888 "88b888 "88b888d8P  Y8b  888 "88bd8P  Y8b888
888  888  888888  888  888888  888  888   88888888  X88K  .d888888888  888  888888  88888888888888  888  88888888888888
Y88b 888 d88PY88b 888 d88PY88b 888 d88Pd8bY8b.    .d8""8b.888  888888  888  888888 d88P888Y8b.   d8b888  888Y8b.    Y88b.
 "Y8888888P"  "Y8888888P"  "Y8888888P" Y8P "Y8888 888  888"Y888888888  888  88888888P" 888 "Y8888Y8P888  888 "Y8888  "Y888
                                                                               888
                                                                               888
                                                                               888
'''

WebSiteContents['www_example_edu'] = '''\
                                                                                    dP                            dP
                                                                                    88                            88
dP  dP  dP dP  dP  dP dP  dP  dP    .d8888b. dP.  .dP .d8888b. 88d8b.d8b.  88d888b. 88 .d8888b.    .d8888b. .d888b88 dP    dP
88  88  88 88  88  88 88  88  88    88ooood8  `8bd8'  88'  `88 88'`88'`88  88'  `88 88 88ooood8    88ooood8 88'  `88 88    88
88.88b.88' 88.88b.88' 88.88b.88' dP 88.  ...  .d88b.  88.  .88 88  88  88  88.  .88 88 88.  ... dP 88.  ... 88.  .88 88.  .88
8888P Y8P  8888P Y8P  8888P Y8P  88 `88888P' dP'  `dP `88888P8 dP  dP  dP  88Y888P' dP `88888P' 88 `88888P' `88888P8 `88888P'
oooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooo~88~oooooooooooooooooooooooooooooooooooooooooooooooo
                                                                           dP
'''

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
        notes: str = ''

    devsvc = GolangDevService( 'amdfxlucas', 'saculolissat@gmx.de' )

    repos = [
            GitRepo( repo_url = 'https://github.com/netsys-lab/pan-lua',
                    repo_branch = 'main',
                    repo_path = '/repos/pan-lua' ),

            GitRepo( repo_url = 'https://github.com/netsys-lab/panapi',
                    repo_branch = 'main',
                    repo_path = '/repos/panapi' ),

             GitRepo( repo_url = 'https://github.com/netsys-lab/scion-sdns',
                    repo_branch = 'main', # new-main
                    repo_path = '/repos/scion-sdns',
                    notes= 'the recursive resolver that must run on the host \
                            instead of the default systemd-resolved.service \
                            it is forked from: https://github.com/semihalev/sdns \
                            note: it depends on github.com/miekg/dns v1.1.63  \
                               github.com/quic-go/quic-go v0.49.0  \
                            ' ),


            GitRepo( repo_url = 'https://github.com/netsys-lab/scion-coredns-doq',
                    repo_branch = 'main', # attempt-rebase
                    repo_path = '/repos/scion-coredns-doq',
                    notes = 'SCION DoQ capable coredns nameserver fork based on caddy  \
                            Also includes RHINE through a modified file plugin \
                        '

                    # upstream coredns: https://github.com/coredns/coredns
                    #       depends on github.com/miekg/dns v1.1.65 (latest version as of 03.05.2025)
                    #               	github.com/quic-go/quic-go v0.50.1
                      ),

            #  our miekg/dns fork uses the latest upstream scion-apps !!
            # This is only required for the 'bat' tools to query a caddy SCION HTTPS server
            GitRepo( repo_url = 'https://github.com/netsys-lab/scion-apps',
                    repo_branch = 'attempt-master-rebase',# TODO rename branch into sth. meaningful like: seed-doq or ngi-search
                    repo_path = '/repos/netsys-scion-apps',
                    notes =' ' ),

            GitRepo( repo_url = 'https://github.com/netsys-lab/exdns',
                     repo_branch = 'master', # master-rebased
                     repo_path = '/repos/exdns',
                     notes='dig like CLI program for issuing test DNS requests to the resolver or NS \
                          forked from https://github.com/miekg/exdns \
                            only dependency is miekg/dns 1.56 \
                            This is our favorite because it has the least dependencies \
                            Our fork is capable of SCION DoQ AND RHINE verification '
                              ),


            GitRepo( repo_url = 'https://github.com/netsys-lab/dns',
                    repo_branch = 'master', # master-rebase
                    repo_path = '/repos/dns',
                    notes='fork of miekg/dns with SCION support'
                    ),


            GitRepo(repo_url = 'https://github.com/scionproto-contrib/http-proxy.git',
                    repo_branch = 'main',
                    repo_path = '/repos/http-proxy',
                    notes='SCION HTTP-proxy functionality' ),


            GitRepo(repo_url = 'https://github.com/scionproto-contrib/caddy-scion',
                    repo_branch = 'main',
                    repo_path = '/repos/caddy-scion',
                    notes='caddy server plugins using the http-proxy module' )

            ]

    '''

        Is there any reason for 'resolveapi' package being a part of miekg/dns fork ?
        Can't we make it a module on its own (not i.e. part of scion-apps pan!!) and get
        one step close to not-needing a separate miekg/dns fork anymore ... !?
        - the dns module already contains 'clientconfig.go' to parse the contents of /etc/resolv.conf


        the miekg/dns fork imports scion-apps to implement SCION DoQ support for the dns-client/server

    '''


    '''NOTES:
    scion-coredns-doq imports miekg/dns fork resolveapi package for secondary file plugin
    to resolve the SNI name of the master DNS server from which to transfer a zone from
    '''

    def install_dev_svc(emu: Emulator, node: Node, devsvc, repos: List[GitRepo] ):

        vnodename = f'dev_{node.getAsn()}_{node.getName()}'
        svc = devsvc.install(vnodename)

        for r in repos:
            svc.checkoutRepo(r.repo_url,r.repo_path, r.repo_branch, AccessMode.shared)

        emu.addBinding(Binding(vnodename, filter=Filter(nodeName=node.getName(),
                                                        asn=node.getAsn(),
                                                        allowBound=True)))

    ases = {}
    brs = defaultdict()
    cses = defaultdict()

    # do not install CoreDNS, sdns etc. binaries since we provide them via the DevService
    # The DNS layers will only generate the config files and set up the certificates
    dns_svc = DomainNameService(dns_setup=OptionRegistry().dns_setup(DNSStack.SCION_DEV))
    minica = MiniCAService()

    web = WebService(kind = WebServerKind.CADDY)

    sdns = DomainNameCachingService(do_enc=True)

    # TODO code duplication - reuse code from 'scion-doq.py' (unittest)
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
    etc_hosts = EtcHosts()

    # TODO code duplication - reuse code from 'scion-doq.py'
    def create_topo():
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

    create_topo()

    from seedemu.utilities import createHostsOnNetwork
    # nodes who should have a DevService installed
    dev_targets = []
    ases_with_hosts = [102, 172, 173, 231, 234, 203, 235, 150, 240 , 242, 241]
    for asn in ases_with_hosts:
        as_ = base.getAutonomousSystem(asn)
        createHostsOnNetwork(emu, as_, 'net0', [])
        hnode = as_.getHost('host_0')
        dev_targets.append(hnode)

    # on the docker-host with the SCION browser extensions do:
    # sudo cp  /tmp/seedemu-minica-wtqc23j8/minica.pem /usr/local/share/ca-certificates/minica.crt && sudo update-ca-certificates
    caStore = RootMiniCAStore(caDomain='seedemu.internal.')

    caServer: MiniCAServer = minica.install('ca-vnode')
    # CA server is bound to the same physical node as 'root-a' to make Emulator happy
    # But since MiniCA server exists only at build time and install() is a no-op this is unproblematic.
    emu.addBinding(Binding('ca-vnode', filter=Filter(asn=235, nodeName='host_0')))
    caServer.setCAStore(caStore)
    caServer.installCACert(Filter())

    # 'entrypoint' into the simulation for browser-extension
    # from docker-host access domains in the simulation through the forwarded port:
    # curl "https://www.example.com:7443" --proxy "https://localhost:9443"
    #            --proxy-header "Proxy-Authorization: Basic cG9saWN5Og==" 
    host_a = base.getAutonomousSystem(102).getHost('host_0')
    host_a.addPortForwarding(8888, 8888, 'tcp')
    host_a.addPortForwarding(9443, 9443, 'tcp')

    sdns_server = sdns.install('sdns-vnode')
    sdns_server.setCAServer(caServer)
    emu.addBinding(Binding('sdns-vnode', filter=Filter(asn=102, nodeName='host_0', allowBound=True)))

    fwdpxy = web.install('fwd_pxy')
    fwdpxy.enableHTTPS()
    fwdpxy.makeForwardProxy()
    fwdpxy.setServerNames(['localhost'])
    fwdpxy.setCAServer(caServer)
    emu.addBinding(Binding('fwd_pxy', filter=Filter(asn=102, nodeName='host_0', allowBound=True)))

    # HTTP (SCION) web server ...........................

    # 'www.example.com'
    host_web_1 = base.getAutonomousSystem(172).getHost('host_0')

    w1 = web.install('web1')
    w1.enableHTTPS()
    w1.setIndexContent(WebSiteContents['index_template'].format(address='1-172,10.172.0.71',
                                                                nodeName='host_0',
                                                                domain='www.example.com',
                                                                body=WebSiteContents['www_example_com'],
                                                                asn=172))
    w1.setServerNames(['www.example.com'])
    w1.setCAServer(caServer)
    emu.addBinding(Binding('web1', filter=Filter(asn=172, nodeName='host_0')))

    # 'www.example.net'
    host_web_2 = base.getAutonomousSystem(173).getHost('host_0')

    w2 = web.install('web2')
    w2.enableHTTPS()
    w2.setIndexContent(WebSiteContents['index_template'].format(address='1-173,10.173.0.71',
                                                                nodeName='host_0',
                                                                domain='www.example.net',
                                                                body=WebSiteContents['www_example_net'],
                                                                asn=173))
    w2.setServerNames(['www.example.net'])
    w2.setCAServer(caServer)
    emu.addBinding(Binding('web2', filter=Filter(asn=173, nodeName='host_0')))

    # 'www.example.edu'
    host_web_3 = base.getAutonomousSystem(241).getHost('host_0')

    w3 = web.install('web3')
    w3.enableHTTPS()
    w3.setServerNames(['www.example.edu'])
    w3.setCAServer(caServer)
    w3.setIndexContent(WebSiteContents['index_template'].format(address='2-241,10.241.0.71',
                                                                nodeName='host_0',
                                                                domain='www.example.edu',
                                                                body=WebSiteContents['www_example_edu'],
                                                                asn=241))
    emu.addBinding(Binding('web3', filter=Filter(asn=241, nodeName='host_0')))



    # coredns DoQ nameservers ..........................................
    # root '.'
    host_ns_1 = base.getAutonomousSystem(235).getHost('host_0')
    host_ns_1.addHostName('scion-root-servers-net.') # will be added to /etc/hosts of all nodes if EtcHosts() layer is present

    root_a = dns_svc.install('root-a')
    root_a.setCAServer(caServer)
    root_a.addZone('.', createNsAndSoa=True).setMaster()
    emu.addBinding(Binding('root-a', filter=Filter(asn=235, nodeName='host_0', allowBound=True)))

    # 'com.' zone
    host_ns_2 = base.getAutonomousSystem(234).getHost('host_0')

    ns_com = dns_svc.install('ns-com') # actually 'ns1-com' to be precise
    ns_com.setCAServer(caServer)
    ns_com.addZone('com.', createNsAndSoa=True).setMaster()
    emu.addBinding(Binding('ns-com', filter=Filter(asn=234, nodeName='host_0')))


    # 'net.'
    host_ns_3 = base.getAutonomousSystem(203).getHost('host_0')

    ns_net = dns_svc.install('ns-net')
    ns_net.setCAServer(caServer)
    ns_net.addZone('net.', createNsAndSoa=True).setMaster()
    emu.addBinding(Binding('ns-net', filter=Filter(asn=203, nodeName='host_0')))

    # 'edu.'
    host_ns_4 = base.getAutonomousSystem(231).getHost('host_0')

    ns_edu = dns_svc.install('ns-edu')
    ns_edu.setCAServer(caServer)
    ns_edu.addZone('edu.', createNsAndSoa=True).setMaster()
    emu.addBinding(Binding('ns-edu', filter=Filter(asn=231, nodeName='host_0')))

    # second level zones name servers

    # 'example.com.'
    host_ns_5 = base.getAutonomousSystem(150).getHost('host_0')

    ns_example_com = dns_svc.install('ns-example.com')
    ns_example_com.setCAServer(caServer)
    ns_example_com.addZone('example.com.', createNsAndSoa=True).setMaster()
    emu.addBinding(Binding('ns-example.com', filter=Filter(asn=150, nodeName='host_0')))

    dns_svc.getZone('example.com.').addRecord(TXT_RR(text='scion=1-172,10.172.0.71', name='www.example.com.'))

    # 'example.net.'
    host_ns_6 = base.getAutonomousSystem(240).getHost('host_0')

    ns_example_net = dns_svc.install('ns-example.net')
    ns_example_net.setCAServer(caServer)
    ns_example_net.addZone('example.net.', createNsAndSoa=True).setMaster()
    emu.addBinding(Binding('ns-example.net', filter=Filter(asn=240, nodeName='host_0')))

    dns_svc.getZone('example.net.').addRecord(TXT_RR(text='scion=1-173,10.173.0.71', name='www.example.net.'))

    # 'example.edu.'
    host_ns_7 = base.getAutonomousSystem(242).getHost('host_0')

    ns_example_edu = dns_svc.install('ns-example.edu')
    ns_example_edu.setCAServer(caServer)
    ns_example_edu.addZone('example.edu.', createNsAndSoa=True).setMaster()
    emu.addBinding(Binding('ns-example.edu', filter=Filter(asn=242, nodeName='host_0')))

    dns_svc.getZone('example.edu.').addRecord(TXT_RR(text='scion=2-241,10.241.0.71', name='www.example.edu.'))

    for node in dev_targets:
        install_dev_svc(emu, node, devsvc, repos )


    # Rendering
    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(scion_isd)
    emu.addLayer(scion)
    emu.addLayer(etc_hosts)
    emu.addLayer(dns_svc)
    emu.addLayer(sdns)
    emu.addLayer(web)
    emu.addLayer(minica)
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