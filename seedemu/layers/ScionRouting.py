from __future__ import annotations
import json
import os.path
from typing import Dict, Tuple
from ipaddress import IPv4Address

import yaml

from seedemu.core import Emulator, Node, ScionAutonomousSystem,AutonomousSystem, ScionRouter, Network
from seedemu.core.enums import NetworkType, NodeRole
from seedemu.layers import Routing, ScionBase, ScionIsd



_Templates: Dict[str, str] = {}

_Templates["general"] = """\
[general]
id = "{name}"
config_dir = "/etc/scion"

[log.console]
level = "{loglevel}"
"""

_Templates["metrics"] = """
[metrics]
prometheus = "{}:{}"
"""

_Templates["router"]  = """
[router]

"""
_Templates["features"] = """
[features]
{}
"""

_Templates["trust_db"] = """\
[trust_db]
connection = "/cache/{name}.trust.db"

"""

_Templates["path_db"]  = """\
[path_db]
connection = "/cache/{name}.path.db"

"""

_Templates["beacon_db"] = """\
[beacon_db]
connection = "/cache/{name}.beacon.db"

"""

_Templates["dispatcher"] = """\
[dispatcher]
id = "dispatcher"
local_udp_forwarding = true

[dispatcher.service_addresses]
"{isd_as},CS" = "{ip}:30254"
"{isd_as},DS" = "{ip}:30254"
"""

_CommandTemplates: Dict[str, str] = {}

_CommandTemplates["br"] = "{cmd} --config /etc/scion/{name}.toml {log}"
_CommandTemplates["br_envsubst"] = "envsubst < /etc/scion/{name}.toml > /etc/scion/_{name}_.toml && {cmd} --config /etc/scion/_{name}_.toml {log}"


_CommandTemplates["cs_no_disp"] = """\
{cmd} --config /etc/scion/{name}.toml {log}\
"""

_CommandTemplates["cs_no_disp_envsubst"] = """\
envsubst < /etc/scion/{name}.toml > /etc/scion/_{name}_.toml && {cmd} --config /etc/scion/_{name}_.toml {log}\
"""

_CommandTemplates["disp"] = "{cmd} --config /etc/scion/dispatcher.toml {log}"

_CommandTemplates["sciond"] = "{cmd} --config /etc/scion/sciond.toml {log}"

_CommandTemplates["disp_envsubst"] = "envsubst < /etc/scion/dispatcher.toml > /etc/scion/_dispatcher_.toml && {cmd} --config /etc/scion/_dispatcher_.toml {log}"

_CommandTemplates["sciond_envsubst"] = "envsubst < /etc/scion/sciond.toml > /etc/scion/_sciond_.toml && {cmd} --config /etc/scion/_sciond_.toml {log}"


class ScionRouting(Routing):
    """!
    @brief Extends the routing layer with SCION inter-AS routing.

    Installs the open-source SCION stack on all hosts and routers. Additionally
    installs standard SCION test applications (e.g., scion-bwtestclient - a
    replacement for iperf) on all hosts.

    During layer configuration Router nodes are replaced with ScionRouters which
    add methods for configuring SCION border router interfaces.
    """
    CMDNAMES: Dict[str,str] = {'router': 'scion-border-router',
                               'control': 'scion-control-service',
                               'dispatcher': 'scion-dispatcher',
                               'daemon': 'sciond' }
    _rotate_logs: bool = False
    _use_envsubst: bool = True
    __disable_bfd: bool = True
    __loglevel: str = 'debug'
    _experimental_scmp: bool =False

    def __init__(self, loopback_range: str = '10.0.0.0/16',
                 rotate_logs: bool = False,
                 disable_bfd: bool = True,
                 use_envsubst:bool = True,
                 loglevel:str = 'debug',
                 experimental_scmp: bool =False ):
        super().__init__(loopback_range)
        ScionRouting._use_envsubst = use_envsubst # TODO: maybe allow scoping of this i.e. override by NodeRole or individual nodes
        ScionRouting._experimental_scmp = experimental_scmp
        ScionRouting.__disable_bfd = disable_bfd
        ScionRouting._rotate_logs = rotate_logs
        ScionRouting.__loglevel= loglevel
            
    @staticmethod
    def _resolveFlag( flag: str , _as: AutonomousSystem, node: Node = None) -> str:
        """!
            @brief return the value of the Flag variable on the given node in the given AS
            Nodes may have overrides of its AS's configuration
            which is in turn an override of the ScionRouting layer defaults
        """

        if flag not in ['loglevel',
                        'disable_bfd',
                        'experimental_scmp',
                        'appropriate_digest']:
            raise ValueError( f"invalid argument - flag {flag} unknown to SCION")
        
        flag_envsub ={'loglevel' : '${LOGLEVEL}',
                      'disable_bfd': "${DISABLE_BFD}",
                      'experimental_scmp': "${EXPERIMENTAL_SCMP}"}
        global_defaults = {'disable_bfd': 'true' if ScionRouting.__disable_bfd else 'false',
                           'experimental_scmp': 'true' if ScionRouting._experimental_scmp else 'false',
                           'loglevel': ScionRouting.__loglevel }
        flag_hardcode = {'loglevel': _as.getFeatures()['loglevel'] if 'loglevel' in _as.getFeatures() else global_defaults["loglevel"],
                         'disable_bfd': _as.getFeatures()['disable_bfd'] if 'disable_bfd' in _as.getFeatures() else global_defaults["disable_bfd"],
                         'experimental_scmp': _as.getFeatures()['experimental_scmp'] if 'experimenta_scmp' in _as.getFeatures() else global_defaults["experimental_scmp"]
                         }
        if ScionRouting._use_envsubst:
            return flag_envsub[flag]
        else:
            return flag_hardcode[flag]

    # TODO: add AS & node as parameter to allow overrides of the global defaults
    @staticmethod
    def disableBFD()-> bool:
        return ScionRouting.__disable_bfd
    
    @staticmethod
    def rotateLogs()-> bool:
        return ScionRouting._rotate_logs
    
    @staticmethod
    def _nameOfCmd( cmd: str):
        """!
        @brief the SCION distributables are named differently in the .deb package,
        than in the actual build
        """
        return ScionRouting.CMDNAMES[cmd]

    def _setScionEnv(self, node: Node, _as: AutonomousSystem):
        """!
        @brief apply the AS default ENV configuration to the given node
        """

        def bool2str(b: bool) -> str:
            return 'true' if b else 'false'

        if not ScionRouting._use_envsubst:
            return
        # these will have to provided inside an '.env' file alongside the docker-compose.yml
        node.setCustomEnv(key='LOGLEVEL',val='${LOGLEVEL}',
                          default_val=_as.getFeatures()['loglevel'] if 'loglevel' in _as.getFeatures() else ScionRouting.__loglevel)

        if node.getRole()==NodeRole.BorderRouter:
            node.setCustomEnv(key='DISABLE_BFD',
                              val='${DISABLE_BFD}',
                              default_val=bool2str(ScionRouting.disableBFD()))            
        
        if node.getRole()==NodeRole.BorderRouter or 'cs' in node.getName():
            node.setCustomEnv(key='EXPERIMENTAL_SCMP',
                              val=f'${{EXPERIMENTAL_SCMP_{node.getAsn()}}}',
                              default_val=_as.getFeatures()['experimental_scmp'] if 'experimental_scmp' in _as.getFeatures() else bool2str(ScionRouting._experimental_scmp))
        #TODO:    node.setCustomEnv( '- APPROPRIATE_DIGEST')


    def configure(self, emulator: Emulator):
        """!
        @brief Install SCION on router, control service and host nodes.
        """
        super().configure(emulator)

        reg = emulator.getRegistry()
        for ((scope, type, name), obj) in reg.getAll().items():
            _as = emulator.getLayer('Base').getAutonomousSystem(obj.getAsn())
            if type in ['hnode', 'csnode', 'brdnode']:
                # set all SCION related ENV variables on the nodes
                self._setScionEnv(obj, _as)
            # SCION inter-domain routing affects only border-routers
            if type == 'brdnode':
                rnode: ScionRouter = obj
                if not issubclass(rnode.__class__, ScionRouter):
                    rnode.__class__ = ScionRouter
                    rnode.initScionRouter()

                self.__install_scion(rnode)
                name = rnode.getName()
                br_log = ">> /var/log/scion-border-router.log 2>&1" if not ScionRouting.rotateLogs() else "2>&1 | rotatelogs -n 2 /var/log/scion-border-router.log 1M "
                router_start_cmd=""
                if ScionRouting._use_envsubst:
                    router_start_cmd=_CommandTemplates['br_envsubst'].format(name=name,cmd=ScionRouting._nameOfCmd('router'),log=br_log)
                else:
                    router_start_cmd=_CommandTemplates['br'].format(name=name,cmd=ScionRouting._nameOfCmd('router'),log=br_log)
                rnode.appendStartCommand(router_start_cmd, fork=True)

              

            elif type == 'csnode':
                csnode: Node = obj
                self.__install_scion(csnode)
                self.__append_scion_command(csnode)
                name = csnode.getName()
                ctrl_log = ">> /var/log/scion-control-service.log 2>&1" if not ScionRouting.rotateLogs() else " 2>&1 | rotatelogs -n 2 /var/log/scion-control-service.log 1M "
                csnode.appendStartCommand(_CommandTemplates['cs_no_disp' + "_envsubst" if ScionRouting._use_envsubst else ''].format(name=name,cmd=ScionRouting._nameOfCmd('control'),log=ctrl_log), fork=True)

            elif type == 'hnode':
                hnode: Node = obj
                self.__install_scion(hnode)
                self.__append_scion_command(hnode)

    def __install_scion(self, node: Node):
        """Install SCION packages on the node."""
        node.addBuildCommand(
            'echo "deb [trusted=yes] https://packages.netsec.inf.ethz.ch/debian all main"'
            ' > /etc/apt/sources.list.d/scionlab.list')
        node.addBuildCommand(
            "apt-get update && apt-get install -y"
            " scion-border-router scion-control-service scion-daemon scion-dispatcher scion-tools"
            " scion-apps-bwtester")
        node.addSoftware("apt-transport-https")
        node.addSoftware("ca-certificates")
        if ScionRouting.rotateLogs():
            node.addSoftware('apache2-utils') # for rotatelogs
        if ScionRouting._use_envsubst: # for envsubst
            node.addSoftware('gettext')

    def __append_scion_command(self, node: Node):
        """Append commands for starting the SCION host stack on the node."""
        disp_log = ">> /var/log/scion-dispatcher.log 2>&1" if not ScionRouting.rotateLogs() else "2>&1 |  rotatelogs -n 2 /var/log/scion-dispatcher.log 1M "
        node.appendStartCommand(_CommandTemplates["disp" + "_envsubst" if ScionRouting._use_envsubst else ''].format(cmd=ScionRouting._nameOfCmd('dispatcher'),log = disp_log ), fork=True)

        sciond_log = ">> /var/log/sciond.log 2>&1" if not ScionRouting.rotateLogs() else " 2>&1 | rotatelogs -n 2 /var/log/sciond.log 1M "
        node.appendStartCommand(_CommandTemplates["sciond"+ "_envsubst" if ScionRouting._use_envsubst else ''].format(cmd=ScionRouting._nameOfCmd('daemon'),log=sciond_log), fork=True)

    def render(self, emulator: Emulator):
        """!
        @brief Configure SCION routing on router, control service and host
        nodes.
        """
        super().render(emulator)
        reg = emulator.getRegistry()
        base_layer: ScionBase = reg.get('seedemu', 'layer', 'Base')
        assert issubclass(base_layer.__class__, ScionBase)
        isd_layer: ScionIsd = reg.get('seedemu', 'layer', 'ScionIsd')

        reg = emulator.getRegistry()
        for ((scope, type, name), obj) in reg.getAll().items():
            if type in ['brdnode', 'csnode', 'hnode']:
                node: Node = obj
                asn = obj.getAsn()                
                as_: ScionAutonomousSystem = base_layer.getAutonomousSystem(asn)
                isds = isd_layer.getAsIsds(asn)
                assert len(isds) == 1, f"AS {asn} must be a member of exactly one ISD"

                # Install AS topology file
                as_topology = as_.getTopology(isds[0][0])
                node.setFile("/etc/scion/topology.json", json.dumps(as_topology, indent=2))

                self.__provision_base_config(node,as_)

            if type == 'brdnode':
                rnode: ScionRouter = obj
                self.__provision_router_config(rnode,as_)
            elif type == 'csnode':
                csnode: Node = obj
                self._provision_cs_config(csnode, as_)
                if as_.getGenerateStaticInfoConfig():
                    self._provision_staticInfo_config(csnode, as_) # provision staticInfoConfig.json
                self.__provision_dispatcher_config(csnode, isds[0][0], as_)
            elif type == 'hnode':
                hnode: Node = obj
                self.__provision_dispatcher_config(hnode, isds[0][0], as_)
    @staticmethod
    def __provision_base_config(node: Node,_as: AutonomousSystem):
        """Set configuration for sciond and dispatcher."""

        node.addBuildCommand("mkdir -p /cache")

        node.setFile("/etc/scion/sciond.toml",
            _Templates["general"].format(name="sd1",
                                         loglevel=ScionRouting._resolveFlag('loglevel',_as)
                                         ) +
            _Templates["trust_db"].format(name="sd1") +
            _Templates["path_db"].format(name="sd1")
            # _Templates["metrics"].format(node.getIPAddress(), 30455)
            # No Features for daemon
            )
    
    @staticmethod
    def __provision_dispatcher_config(node: Node, isd: int, as_: ScionAutonomousSystem):
        """Set dispatcher configuration on host and cs nodes."""

        isd_as = f"{isd}-{as_.getAsn()}"
        
        ip = None
        ifaces = node.getInterfaces()
        if len(ifaces) < 1:
            raise ValueError(f"Node {node.getName()} has no interfaces")
        net = ifaces[0].getNet()                    
        control_services = as_.getControlServices()
        for cs in control_services:
            cs_iface = as_.getControlService(cs).getInterfaces()[0]
            if cs_iface.getNet() == net:
                ip = cs_iface.getAddress()
                break        
        if ip is None:
            raise ValueError(f"Node {node.getName()} has no interface in the control service network")
        
        node.setFile("/etc/scion/dispatcher.toml",
                      _Templates["dispatcher"].format(isd_as=isd_as, ip=ip)
                      # _Templates["metrics"].format(addr:=node.getIPAddress(),port:=30441) 
                      )

    @staticmethod
    def __provision_router_config(router: ScionRouter, _as: AutonomousSystem ):
        """Set border router configuration on router nodes."""

        name = router.getName()
        config_content = _Templates["general"].format(name=name,
                                                      loglevel=ScionRouting._resolveFlag('loglevel',_as))
        # config_content += _Templates["metrics"].format(addr:=router.getIPAddress(), port:=30442)
        _keyvals_router = [ "bfd.disable={}".format(ScionRouting._resolveFlag('disable_bfd',_as)) ]
        _kvals_features = [
            f"experimental_scmp_authentication={ScionRouting._resolveFlag('experimental_scmp',_as)}" ]

        config_content += _Templates["router"] +'\n'+ '\n'.join(_keyvals_router) + '\n'
        if len(_kvals_features) > 0:
            config_content += _Templates['features'].format('\n'.join(_kvals_features) )

        router.setFile(os.path.join("/etc/scion/", name + ".toml"), config_content)
    
    @staticmethod
    def _get_networks_from_router(router1 : str, router2 : str, as_ : ScionAutonomousSystem) -> list[Network]:
        """
        gets all networks that both router1 and router2 are part of

        NOTE: assume that any two routers in an AS are connected through a network
        """
        br1 = as_.getRouter(router1)
        br2 = as_.getRouter(router2)
        # create list of all networks router is in
        br1_nets = [intf.getNet().getName() for intf in br1.getInterfaces()]
        br2_nets = [intf.getNet().getName() for intf in br2.getInterfaces()]
        # find common nets
        joint_nets = [as_.getNetwork(net) for net in br1_nets if net in br2_nets]
        # return first one
        try:
            return joint_nets[0]
        except:
            raise Exception(f"No common network between {router1} and {router2} but they are in the same AS")
    
    @staticmethod
    def _get_BR_from_interface(interface : int, as_ : ScionAutonomousSystem) -> str:
        """
        gets the name of the border router that the ScionInterface is connected to
        """
        # find name of this brd
        for br in as_.getBorderRouters():
            if interface in as_.getRouter(br).getScionInterfaces():
                return br

    @staticmethod
    def _get_internal_link_properties(interface : int, as_ : ScionAutonomousSystem) -> Dict[str, Dict]:
        """
        Gets the internal Link Properties to all other Scion interfaces from the given interface
        """

        this_br_name = ScionRouting._get_BR_from_interface(interface, as_)
        
        ifs = {
            "Latency": {},
            "Bandwidth": {},
            "packetDrop": {},
            "MTU": {},
            "Hops": {},
            "Geo": {},
        }

        # get Geo information for this interface if it exists
        if as_.getRouter(this_br_name).getGeo():
            (lat,long,address) = as_.getRouter(this_br_name).getGeo()
            ifs["Geo"] = {
                "Latitude": lat,
                "Longitude": long,
                "Address": address
            }

        # iterate through all border routers to find latency to all interfaces
        for br_str in as_.getBorderRouters():
            br = as_.getRouter(br_str)
            scion_ifs = br.getScionInterfaces()
            # find latency to all interfaces except itself
            for other_if in scion_ifs:
                if other_if != interface:
                    # if interfaces are on same router latency is 0ms
                    if br_str == this_br_name:
                        ifs["Latency"][str(other_if)] =  "0ms"
                        # NOTE: omit bandwidth as it is limited by cpu if the interfaces are on the same router
                        ifs["packetDrop"][str(other_if)] =  "0.0"
                        # NOTE: omit MTU if interfaces are on same router as this depends on the router
                        ifs["Hops"][str(other_if)] =  0 # if interface is on same router, hops is 0
                    else:
                        net = ScionRouting._get_networks_from_router(this_br_name, br_str, as_) # get network between the two routers (Assume any two routers in AS are connected through a network)
                        (latency, bandwidth, packetDrop) = net.getDefaultLinkProperties()
                        mtu = net.getMtu()
                        ifs["Latency"][str(other_if)] =  f"{latency}ms"
                        if bandwidth != 0: # if bandwidth is not 0, add it
                            ifs["Bandwidth"][str(other_if)] =  int(bandwidth/1000) # convert bps to kbps
                        ifs["packetDrop"][str(other_if)] =  f"{packetDrop}"
                        ifs["MTU"][str(other_if)] =  f"{mtu}"
                        ifs["Hops"][str(other_if)] =  1 # NOTE: if interface is on different router, hops is 1 since we assume all routers are connected through a network
        
        
        return ifs

    @staticmethod
    def _get_xc_link_properties(interface : int, as_ : ScionAutonomousSystem) -> Tuple[int, int, float, int]:
        """
        get cross connect link properties from the given interface
        """
        this_br_name = ScionRouting._get_BR_from_interface(interface, as_)
        this_br = as_.getRouter(this_br_name)

        if_addr = this_br.getScionInterface(interface)['underlay']["public"].split(':')[0]

        xcs = this_br.getCrossConnects()

        for xc in xcs:  
            (xc_if,_,linkprops) = xcs[xc]
            if if_addr == str(xc_if.ip):
                return linkprops
                    
    @staticmethod
    def _get_ix_link_properties(interface : int, as_ : ScionAutonomousSystem) -> Tuple[int, int, float, int]:
        """
        get internet exchange link properties from the given interface
        """
        this_br_name = ScionRouting._get_BR_from_interface(interface, as_)
        this_br = as_.getRouter(this_br_name)

        if_addr = IPv4Address(this_br.getScionInterface(interface)['underlay']["public"].split(':')[0])
        
        # get a list of all ix networks this Border Router is attached to
        ixs = [ifa.getNet() for ifa in this_br.getInterfaces() if ifa.getNet().getType() == NetworkType.InternetExchange]

        for ix in ixs:  
            ix.getPrefix()
            if if_addr in ix.getPrefix():
                lat,bw,pd = ix.getDefaultLinkProperties()
                mtu = ix.getMtu()
                return lat,bw,pd,mtu

    @staticmethod
    def _provision_staticInfo_config(node: Node, as_: ScionAutonomousSystem):
        """
        Set staticInfo configuration.

        NOTE: Links also have PacketDrop and MTU, which could be added if it was supported by staticInfoConjg.json file
        """

        staticInfo = {
            "Latency": {},
            "Bandwidth": {},
            "LinkType": {},
            "Geo": {},
            "Hops": {},
            "Note": ""
        }

        # iterate through all ScionInterfaces in AS
        for interface in range(1,as_._ScionAutonomousSystem__next_ifid):

            ifs = ScionRouting._get_internal_link_properties(interface, as_)
            xc_linkprops = ScionRouting._get_xc_link_properties(interface, as_)
            if xc_linkprops:
                lat,bw,pd,mtu = xc_linkprops
            else: # interface is not part of a cross connect thus it must be in an internet exchange
                lat,bw,pd,mtu = ScionRouting._get_ix_link_properties(interface, as_)
            

            # Add Latency
            if lat != 0: # if latency is not 0, add it
                if not staticInfo["Latency"]: # if no latencies have been added yet empty dict
                    staticInfo["Latency"][str(interface)] = {}
                staticInfo["Latency"][str(interface)]["Inter"] = str(lat)+"ms"
            for _if in ifs["Latency"]: # add intra latency
                if ifs["Latency"][_if] != "0ms": # omit 0ms latency
                    if not staticInfo["Latency"][str(interface)]["Intra"]: # if no intra latencies have been added yet empty dict
                        staticInfo["Latency"][str(interface)]["Intra"] = {}
                    staticInfo["Latency"][str(interface)]["Intra"][str(_if)] = ifs["Latency"][_if]
            
            
            
            # Add Bandwidth
            if bw != 0: # if bandwidth is not 0, add it
                if not staticInfo["Bandwidth"]: # if no bandwidths have been added yet empty dict
                    staticInfo["Bandwidth"][str(interface)] = {}
                staticInfo["Bandwidth"][str(interface)]["Inter"] = int(bw/1000) # convert bps to kbps
            if ifs["Bandwidth"]: # add intra bandwidth
                staticInfo["Bandwidth"][str(interface)]["Intra"] = ifs["Bandwidth"]

            # Add LinkType
            staticInfo["LinkType"][str(interface)] = "direct" # NOTE: for now all ASes are connected through CrossConnects which are docker Nets under the hood and thus direct
             
            # Add Geo
            if ifs["Geo"]:
                staticInfo["Geo"][str(interface)] = ifs["Geo"]

            # Add Hops 
            staticInfo["Hops"][str(interface)] = {
                "Intra": ifs["Hops"],
            }

        # Add Note if exists
        if as_.getNote():
            staticInfo["Note"] = as_.getNote()
        
        # Set file
        node.setFile("/etc/scion/staticInfoConfig.json", json.dumps(staticInfo, indent=2))

    @staticmethod
    def _provision_cs_config(node: Node, as_: ScionAutonomousSystem):
        """Set control service configuration."""

        # Start building the beaconing section
        beaconing = ["[beaconing]"]
        interval_keys = ["origination_interval", "propagation_interval", "registration_interval"]
        for key, value in zip(interval_keys, as_.getBeaconingIntervals()):
            if value is not None:
                beaconing.append(f'{key} = "{value}"')

        # Create policy files
        beaconing.append("\n[beaconing.policies]")
        for type in ["propagation", "core_registration", "up_registration", "down_registration"]:
            policy = as_.getBeaconingPolicy(type)
            if policy is not None:
                file_name = f"/etc/scion/{type}_policy.yaml"
                node.setFile(file_name, yaml.dump(policy, indent=2))
                beaconing.append(f'{type} = "{file_name}"')

        # Concatenate configuration sections
        name = node.getName()
        _features =[  f"experimental_scmp={ScionRouting._resolveFlag('experimental_scmp', as_)}" if ScionRouting._experimental_scmp else ''
                  # f"appropriate_digest_algorithm={self.resolveFlag('appropriate_digest',as_)}"
                   ]
        node.setFile(os.path.join("/etc/scion/", name + ".toml"),
            _Templates["general"].format(name=name,
            loglevel=ScionRouting._resolveFlag('loglevel',as_)) +
            _Templates["trust_db"].format(name=name) +
            _Templates["beacon_db"].format(name=name) +
            _Templates["path_db"].format(name=name) +
             # _Templates["metrics"].format(node.getIPAddress(), 30452)  +
            _Templates['features'].format('\n'.join(_features)) +
            "\n".join(beaconing))
