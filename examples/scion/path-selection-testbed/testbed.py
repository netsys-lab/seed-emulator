#!/usr/bin/env python3

from seedemu.compiler import Docker, Graphviz
from seedemu.core import Emulator, OptionMode, OptionRegistry
from seedemu.layers import (
    ScionBase, ScionRouting, ScionIsd, Scion, SetupSpecification, Ospf, Ibgp, Ebgp, PeerRelationship)
from seedemu.layers.Scion import LinkType as ScLinkType
import json
from generate_scripts import generate_scripts
import shutil

# Initialize
emu = Emulator()
base = ScionBase()

spec = SetupSpecification.PACKAGES()
routing = ScionRouting(setup_spec=OptionRegistry().scion_setup_spec(spec))
ospf = Ospf()
scion_isd = ScionIsd()
scion = Scion()
ibgp = Ibgp()
ebgp = Ebgp()

INSTALL_STK_SERVER = True
SETUP_MACVLAN = False

if INSTALL_STK_SERVER:
    from utils import init_db, svn_checkout, git_clone, init_db, add_macvlan_docker_compose


# load topo.json to dict
topo = json.load(open('topo/topo.json'))

# Create isolation domains
for isd in topo['ISDs']:
    base.createIsolationDomain(isd)

# Create ixs
for link in topo['links']:
    base.createInternetExchange(link['id'], create_rs=True)

dashboard_asn = topo['dashboard_asn']
client1_asn = topo['client1_asn']
client2_asn = topo['client2_asn']
# Create ASes
for as__ in topo['ASes']:
    asn = as__['asn']
    isd = as__['isd']
    is_core = as__['is_core_as']
    as_ = base.createAutonomousSystem(asn)
    scion_isd.addIsdAs(isd, asn, is_core=is_core)
    if not is_core:
        issuer = as__['cert_issuer']
        scion_isd.setCertIssuer((isd, asn), issuer=issuer)
    
    as_.createNetwork('net0')  
    as_.createControlService('cs0').joinNetwork('net0')
    as_br0 = as_.createRouter('br0')
    as_br0.joinNetwork('net0')    
    as_br0.addSoftware("iperf3")
    as_br0.addSoftware("python3")
    as_br0.addSoftware("python3-pip")
    as_br0.addBuildCommand('pip3 install paho-mqtt psutil')
    as_br0.addSharedFolder("/node", "../node")

    ixes = [link['id'] for link in topo['links'] if link['source_asn'] == asn or link['dest_asn'] == asn]
    for ix in ixes:
        as_br0.joinNetwork('ix{}'.format(ix))

    if asn == dashboard_asn:
        h1 = as_.createHost('h1').joinNetwork('net0')  
        h1.addSoftware("iperf3")
        h1.addSoftware("mosquitto")
        h1.addSoftware("python3")
        h1.addSoftware("python3-pip")
        h1.addSoftware("socat")
        h1.addSoftware("wireguard-tools")
        h1.addBuildCommand('pip3 install paho-mqtt')
        # h1.addBuildCommand('pip3 install psutil pyserial pygame requests numpy deap token-bucket')
        h1.addBuildCommand('pip3 install dash dash-cytoscape dash-bootstrap-components dash-daq numpy')
        h1.addPortForwarding(1883, 1883)
        h1.addPortForwarding(8050 , 8050)
        h1.addPortForwarding(28015, 28015)
        h1.addSharedFolder("/topo", "../topo")
        h1.addSharedFolder("/dashboard", "../dashboard")
        h1.addSharedFolder("/wireguard", "../wireguard")
        h1.addSharedFolder("/server", "../server")
        if INSTALL_STK_SERVER:
            h1.addDockerCommand('COPY stk-code /src/stk-code')
            h1.addDockerCommand('COPY stk-assets /src/stk-assets')
            h1.addSoftware("git cmake make g++ libenet-dev libssl-dev libsdl2-dev build-essential")
            h1.addSoftware("libogg-dev libvorbis-dev libopenal-dev libfreetype6-dev subversion")
            h1.addSoftware("libgl1-mesa-dev libcurl4-openssl-dev libsqlite3-dev pkg-config")
            h1.addBuildCommand('mkdir -p /src/stk-code/build && \
                cd /src/stk-code/build && \
                cmake .. -DSERVER_ONLY=ON -DUSE_SQLITE3=ON -DCMAKE_BUILD_TYPE=Release && \
                make -j$(nproc) && \
                make install')
            h1.addPortForwarding(2759, 2759, proto="udp")
    if asn == client1_asn:
        h1 = as_.createHost('h1').joinNetwork('net0')  
        h1.addSoftware("iperf3")
        h1.addSoftware("python3")
        h1.addSoftware("socat")
        h1.addSoftware("wireguard-tools")
        h1.addSoftware("python3-pip")
        h1.addBuildCommand('pip3 install paho-mqtt')
        h1.addBuildCommand('pip3 install pyyaml flask numpy iperf3 ping3 scapy')
        h1.addSharedFolder("/client1", "../client1")
        h1.addSharedFolder("/topo", "../topo")
        h1.addSharedFolder("/wireguard", "../wireguard")
        h1.addPortForwarding(5000, 5000, proto="udp")  
        h1.addPortForwarding(28016, 28015)
    if asn == client2_asn:
        h1 = as_.createHost('h1').joinNetwork('net0')  
        h1.addSoftware("iperf3")
        h1.addSoftware("python3")
        h1.addSoftware("socat")
        h1.addSoftware("wireguard-tools")
        h1.addSoftware("python3-pip")
        h1.addBuildCommand('pip3 install paho-mqtt')
        h1.addBuildCommand('pip3 install pyyaml flask numpy iperf3 ping3 scapy')
        h1.addSharedFolder("/client2", "../client2")
        h1.addSharedFolder("/topo", "../topo")
        h1.addSharedFolder("/wireguard", "../wireguard")
        h1.addPortForwarding(5006, 5006)
        h1.addPortForwarding(28017, 28015)


# add scion and bgp links
for link in topo['links']:
    id = link['id']
    source_asn = link['source_asn']
    source_isd  = 1
    for as__ in topo['ASes']:
        if as__['asn'] == source_asn:
            source_isd = as__['isd']
            break
    dest_isd = 1
    for as__ in topo['ASes']:
        if as__['asn'] == link['dest_asn']:
            dest_isd = as__['isd']
            break

    dest_asn = link['dest_asn']
    link_type = ScLinkType.Transit
    link_type_bgp = PeerRelationship.Provider
    if link['is_core_link'] == True:
        link_type = ScLinkType.Core
        link_type_bgp = PeerRelationship.Peer
    
    scion.addIxLink(id, (source_isd, source_asn), (dest_isd, dest_asn), link_type)
    ebgp.addPrivatePeering(id, source_asn, dest_asn, PeerRelationship.Provider)

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
emu.compile(Docker(), './output', override=True)
emu.compile(Graphviz(), "./output/graphs", override=True)

generate_scripts(topo)

if INSTALL_STK_SERVER:
    svn_repo = "https://svn.code.sf.net/p/supertuxkart/code/stk-assets"
    svn_dest = "stk-assets"
    git_repo = "https://github.com/supertuxkart/stk-code"
    git_dest = "stk-code"

    svn_checkout(svn_repo, svn_dest)
    git_clone(git_repo, git_dest)
    init_db("server/stkservers.db", "server/stk_schema.sql")

    shutil.copytree(svn_dest, "output/hnode_{}_h1/stk-assets".format(dashboard_asn))
    shutil.copytree(git_dest, "output/hnode_{}_h1/stk-code".format(dashboard_asn))

    if SETUP_MACVLAN:
        container_c1 = 'hnode_{}_h1'.format(client1_asn)
        container_c2 = 'hnode_{}_h1'.format(client2_asn)
        net_pc1 = 'pc1-lan'
        net_pc2 = 'pc2-lan'
        dev_pc1 = 'enp0s1'
        dev_pc2 = 'enp0s1'
        gateway_ip1 = '172.16.0.1'
        gateway_ip2 = '172.18.0.1'
        ip_address_c1 = '172.16.0.10'
        ip_address_c2 = '172.18.0.10'

        add_macvlan_docker_compose(container_c1, net_pc1, gateway_ip1, ip_address_c1, dev_pc1)
        add_macvlan_docker_compose(container_c2, net_pc2, gateway_ip2, ip_address_c2, dev_pc2)
