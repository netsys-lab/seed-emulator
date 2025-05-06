from __future__ import annotations
from seedemu.core import Configurable, Service, Server
from seedemu.core import Node, ScopedRegistry, Emulator, CAServerBase
from .DomainNameService import DomainNameService
from .DNSCommon import *
from typing import List, Dict, Tuple
from seedemu.core.enums import NetworkType

DomainNameCachingServiceFileTemplates: Dict[str, str] = {}


DomainNameCachingServiceFileTemplates['sdns_conf_new'] = '''\
bind = "{bind_addr_port}"
{bindsdoq}

# Enable SCION
scion = true
lookupscionaddresseager = true
donottalktootherthanscion = true

# RHINE certificate to validate RRs with
cacertificatefile = "{rhine_cert}"

# Root zone SCION servers
namedRootSCIONServers = [
{scion_root_hints}
]

loglevel = "debug"

# Which clients allowed to make queries
accesslist = [
"0.0.0.0/0",
"::0/0"
]
# TLS certificate file
tlscertificate = "{cert_path}"

# TLS private key file
tlsprivatekey = "{key_path}"
'''



# configuration for sdns recursive resolver
# to function as a drop-in SCION replacement for the system resolver on every host
# and optionally as a public resolver
DomainNameCachingServiceFileTemplates['sdns_conf'] = '''\
bind = "{bind_addr_port}"
{bindsdoq}

# Enable SCION
scion = true

# RHINE certificate to validate RRs with
cacertificatefile = "{rhine_cert}"

# Root zone SCION servers
rootscionservers = [
{scion_root_hints}
]

loglevel = "debug"

# Which clients allowed to make queries
accesslist = [
"0.0.0.0/0",
"::0/0"
]
# TLS certificate file
tlscertificate = "{cert_path}"

# TLS private key file
tlsprivatekey = "{key_path}"
'''

DomainNameCachingServiceFileTemplates['sdns_conf_full'] = '''\
# Address to bind to for the DNS server
#bind = "0.0.0.0:5553"
bind = "127.0.0.1:5553"
#bind = "10.0.2.15:5553"


# Root zone SCION servers
rootscionservers = [
"17-ffaa:1:1008,127.0.0.1:53",
"19-ffaa:1:fe4,127.0.0.1:53" # rhine.ovgu.scionlab.
]

# What kind of information should be logged, Log verbosity level [crit,error,warn,info,debug]
loglevel = "debug"

# List of locations to recursively read blocklists from (warning, every file found is assumed to be a hosts-file or domain list)
blocklistdir = "bl"

# Which clients allowed to make queries
accesslist = [
"0.0.0.0/0",
"::0/0"
]

#--------------------------------------------------------------------------------
# Config version, config and build versions can be different.
version = "1.2.0"

# Address to bind to for the DNS-over-TLS server
#bindtls = ":8853"

# Address to bind to for the DNS-over-HTTPS server
# binddoh = ":8053"

# Outbound ipv4 addresses, if you set multiple, sdns can use random outbound ipv4 address by request based
#outboundips = [
#    "10.0.2.15:3333"
#  "127.0.0.1"
#]

# Outbound ipv6 addresses, if you set multiple, sdns can use random outbound ipv6 address by request based
outboundip6s = [
]

# Root zone ipv4 servers
rootservers = [
"192.5.5.241:53",
"198.41.0.4:53",
"192.228.79.201:53",
"192.33.4.12:53",
"199.7.91.13:53",
"192.203.230.10:53",
"192.112.36.4:53",
"128.63.2.53:53",
"192.36.148.17:53",
"192.58.128.30:53",
"193.0.14.129:53",
"199.7.83.42:53",
"202.12.27.33:53"
]

# Root zone ipv6 servers
root6servers = [
#"[2001:500:2f::f]:53",
#"[2001:503:ba3e::2:30]:53",
#"[2001:500:200::b]:53",
#"[2001:500:2::c]:53",
#"[2001:500:2d::d]:53",
#"[2001:500:a8::e]:53",
#"[2001:500:12::d0d]:53",
#"[2001:500:1::53]:53",
#"[2001:7fe::53]:53",
#"[2001:503:c27::2:30]:53",
#"[2001:7fd::1]:53",
#"[2001:500:9f::42]:53",
#"[2001:dc3::35]:53"
]

# Trusted anchors for dnssec
rootkeys = [
".			172800	IN	DNSKEY	257 3 8 AwEAAaz/tAm8yTn4Mfeh5eyI96WSVexTBAvkMgJzkKTOiW1vkIbzxeF3+/4RgWOq7HrxRixHlFlExOLAJr5emLvN7SWXgnLh4+B5xQlNVz8Og8kvArMtNROxVQuCaSnIDdD5LKyWbRd2n9WGe2R8PzgCmr3EgVLrjyBxWezF0jLHwVN8efS3rCj/EWgvIWgb9tarpVUDK/b58Da+sqqls3eNbuv7pr+eoZG+SrDK6nWeL3c6H5Apxz7LjVc1uTIdsIXxuOLYA4/ilBmSVIzuDWfdRUfhHdY6+cn8HFRm+2hM8AnXGXws9555KrUB5qihylGa8subX2Nn6UwNR1AkUTV74bU="
]

# Failover resolver ipv4 or ipv6 addresses with port, left blank for disabled"
# fallbackservers = [
#	"8.8.8.8:53",
#	"8.8.4.4:53"
# ]
fallbackservers = [
]

# Forwarder resolver ipv4 or ipv6 addresses with port, left blank for disabled"
# forwarderservers = [
#	"8.8.8.8:53",
#	"8.8.4.4:53"
# ]
forwarderservers = [
]

# Address to bind to for the http API server, left blank for disabled
api = "127.0.0.1:8081"

# What kind of information should be logged, Log verbosity level [crit,error,warn,info,debug]
#loglevel = "debug"

# The location of access log file, left blank for disabled. SDNS uses Common Log Format by default.
# accesslog = ""

# List of locations to recursively read blocklists from (warning, every file found is assumed to be a hosts-file or domain list)
#blocklistdir = "bl"


# Enables serving zone data from a hosts file, left blank for disabled
# the form of the entries in the /etc/hosts file are based on IETF RFC 952 which was updated by IETF RFC 1123.
hostsfile = ""

# Network timeout for each dns lookups in duration
timeout = "3s"

# Default error cache TTL in seconds
expire = 600

# Cache size (total records in cache)
cachesize = 256000

# Maximum iteration depth for a query
maxdepth = 30

# Query based ratelimit per second, 0 for disabled
ratelimit = 0

# Client ip address based ratelimit per minute, 0 for disabled
clientratelimit = 0

# DNS server identifier (RFC 5001), it's useful while operating multiple sdns. left blank for disabled
nsid = ""


# Qname minimization level. If higher, it can be more complex and impact the response performance.
# If set 0, qname minimization will be disable
qname_min_level = 5
'''


DomainNameCachingServiceFileTemplates['named_options'] = '''\
options {
    directory "/var/cache/bind";
    recursion yes;
    dnssec-validation no;
    empty-zones-enable no;
    allow-query { any; };
};
'''

def getNodeAddr(node: Node) -> str:
    address = getIpAddr(node)
    if 'scion_address' in node.getLabel():
        scion_addr = node.getLabel()['scion_address']
        ia_str = scion_addr.split(',')[0]
        ip_str = scion_addr.split(',')[1]
        assert ip_str==str(address), 'implementation error'
        return scion_addr
    else:
        return str(address)

def getIpAddr(node: Node) -> str:
    ifaces = node.getInterfaces()
    assert len(ifaces) > 0, 'Node {} has no IP address.'.format(node.getName())
    assert len(ifaces) == 1, f'Node {node.getName()} is not and end-host'
    for iface in ifaces:
        net = iface.getNet()
        if net.getType() == NetworkType.Local:
            address = iface.getAddress()
            return address
    return ""

class DomainNameCachingServer(Server, Configurable):
    """!
    @brief Caching DNS server (i.e., Local DNS server)

    @todo DNSSEC
    """
    __node: Node
    __server_name: str
    __do_enc: bool
    __root_servers: List[str]
    __wipe_docker_resolv_conf: bool
    __configure_resolvconf: bool
    __emulator: Emulator
    __pending_forward_zones: Dict[str, str]
    __asn_range: List[int]
    __is_range_all: bool

    def __init__(self, do_enc: bool, server_name: str = None, wipe_docker_resolv_conf: bool = False):
        """!
        @brief DomainNameCachingServer constructor.
        @param do_enc enable DNS over encrypted transport
        @param wipe_docker_resolv_conf  whether to wipe out the default docker container configuration
                'nameserver 127.0.0.11' (system resolver)
        """
        self.__configured = False
        super().__init__()
        self.__node = None
        self.__wipe_docker_resolv_conf = wipe_docker_resolv_conf
        self.__server_name = server_name
        self.__do_enc = do_enc
        self.__root_servers = []
        self.__enable_https_func = None
        self.__configure_resolvconf = False
        self.__pending_forward_zones = {}
        self.__asn_range = []
        self.__is_range_all = False
        self.__doq_port = 853 # DoQ standart port

    def setCAServer(self, server: CAServerBase):
        assert self.__do_enc, 'logic error'
        """
        """
        self.__enable_https_func = server.enableHTTPSFunc


    def setConfigureResolvconf(self, configure: bool) -> DomainNameCachingServer:
        """!
        @brief Enable or disable set resolv.conf. When true, resolv.conf of all
        other nodes in the AS will be set to this server.

        @returns self, for chaining API calls.
        """
        self.__configure_resolvconf = configure

        return self

    def setRootServers(self, servers: List[str]) -> DomainNameCachingServer:
        """!
        @brief Change root server hint.

        By default, the caching server uses the root hint file shipped with
        bind9. Use this method to override root hint. Note that if autoRoot is
        set to true in DomainNameCachingService, manual changes will be
        overridden.

        @param servers list of IP or SCION addresses of the root servers.

        @returns self, for chaining API calls.
        """
        self.__root_servers = servers

        return self

    def getRootServers(self) -> List[str]:
        """!
        @brief Get root server list.

        By default, the caching server uses the root hint file shipped with
        bind9. Use setRootServers to override root hint.

        This method will return list of servers set by setRootServers, or an
        empty list if not set.
        """
        return self.__root_servers

    def addForwardZone(self, zone: str, vnode: str) -> DomainNameCachingServer:
        """!
        @brief Add a new forward zone, forward to the given virtual node name.

        @param name zone name.
        @param vnode  virtual node name.

        @returns self, for chaining API calls.
        """
        self.__pending_forward_zones[zone] = vnode

        return self

    def setNameServerOnNodesByAsns(self, asns: List[int]):
        """
        adds the hosts in the given ASes to this servers catchment
        """
        self.__asn_range.extend(asns)

    def setNameServerOnAllNodes(self):
        self.__is_range_all = True

    def getServerName(self) -> str:
        """
        the server name of the TLS certificate that this CachingServer
        presents to its clients for DoE
        """
        regInfo = self.__node.getRegistryInfo()
        host_id = regInfo[2].replace('_', '') # or use custom host name if present
        return self.__server_name if self.__server_name != None else f'sdns.{host_id}.{regInfo[0]}.'

    def _getCryptoPaths(self) -> Tuple[str, str]:
        """ return where to find the certificate and private key
        """
        if self.__node.getOption('dns_setup').value in [ DNSStack.SCION, DNSStack.SCION_DEV]:
            cert_path = f'/etc/sdns/ca/{self.getServerName()}-cert.pem'
            key_path = f'/etc/sdns/ca/{self.getServerName()}-key.pem'
        else:
            cert_path = f'/etc/bind9/ca/{self.getServerName()}-cert.pem'
            key_path = f'/etc/bind9/ca/{self.getServerName()}-key.pem'

        return (cert_path, key_path)

    def configure(self, emulator: Emulator, node:Node):
        assert not self.__configured, 'implementation error'
        self.__configured = True
        self.__emulator = emulator
        self.__node = node

        address = getNodeAddr(node)

        assert address != "", 'address is not configured.'

        if node.getOption('dns_setup').value in [DNSStack.SCION, DNSStack.SCION_DEV]:

            if not self.getIsPublicResolver():
                error_msg =  'logic error: this node already had nameservers configured with setNameServers()'
                assert not any(command[0] == ': > /etc/resolv.conf' for command in node.getStartCommands()), error_msg
                assert len(node.getNameServers())==0, error_msg
                s = '127.0.0.127' # FIXME this ought to be a property of 'self'
                node.setNameServers([s])
                # wipe default docker generated contents of resolv.conf
                node.insertStartCommand(0,': > /etc/resolv.conf')
                node.insertStartCommand(1, 'echo "nameserver {}" >> /etc/resolv.conf'.format(s))


            cert_path, key_path = self._getCryptoPaths()
            # request a certificate for the resolvers server-name from the CA
            self.__enable_https_func(node=node,
                                context='sdns',
                                server_names=[self.getServerName()],
                                dst_cert_path=cert_path,
                                dst_key_path=key_path)

        if not self.__is_range_all and len(self.__asn_range) == 0:
            #quic out in case of empty catchment
            return

        self._configureResolverCatchment(address, node)

    def _configureResolverCatchment(self, address: str):
        """
        configures all nodes which fall within this resolver's asn_range
        to use this resolver, by adding it to their /etc/resolv.conf files

        @param address  the IP or SCION address under which it listens for client requests
        @note by default a resolvers catchment is empty (zero ASN_range)
        """
        reg = self.__emulator.getRegistry()
        for ((scope, type, name), node) in reg.getAll().items():
            if type in ['hnode', 'rnode']:
                if self.getIsNodeWithinCatchment(node):
                    # ': > /etc/resolv.conf' wipes the contents of the file
                    if not any(command[0] == ': > /etc/resolv.conf' for command in node.getStartCommands()):
                        node.insertStartCommand(0,': > /etc/resolv.conf')
                        # TODO branch on self.__wipe_docker_resolv_conf and discard
                        # the existing contents only if desired, rather than >> appending to them
                    node.insertStartCommand(1, 'echo "nameserver {}" >> /etc/resolv.conf'.format(address))


    def getIsNodeWithinCatchment(self, node: Node) -> bool:
        """
        return whether the given node shall be configured to use this resolver
        """
        return self.__is_range_all or node.getAsn() in self.__asn_range

    def getIsPublicResolver(self) -> bool:
        """ a public resolver listens on at least one non-loopback address
            that is reachable for other client hosts in its catchment.
            @note only callable after node is configured
        """
        if not self.__is_range_all and len(self.__asn_range) == 0:
            # quick out or empty-catchment
            return False

        # it migh still be possible that the resolvers catchmet AS contains no hosts ...
        reg = self.__emulator.getRegistry()
        for ((scope, type, name), node) in reg.getAll().items():
            if type in ['hnode', 'rnode']:
                if self.getIsNodeWithinCatchment(node):
                    return True
        return False

    def install(self, node: Node):
        """ only called when the server is already configured
        """
        opt = node.getOption('dns_setup')
        if opt == None:
            for o in DomainNameService.getAvailableOptions():
                node.setOption(o)
        if (val:=node.getOption('dns_setup').value) == DNSStack.DEFAULT:
            if self.__do_enc:
                raise NotImplementedError
            self._do_install_bind9(node)
        elif val in [DNSStack.SCION, DNSStack.SCION_DEV]:
            assert self.__do_enc, 'No support for unencrypted DNS (Do53) in the Future Next Generation Internet anymore !'
            self._do_install_sdns(node, val.getHelper())

    def bindDo53AddrPort(self) -> str:
        """where to listen on localhost
        """
        return '127.0.0.127:53'

    def bindDoQAddrPort(self, node: Node) -> str:
        """where to listen for public resolver"""
        return f'{self.getNodeAddr(node)}:{self.__doq_port}'

    def _do_install_sdns(self, node: Node, helper: DNSStackHelperBase):
        """
        install the sdns recursive resolver on the node
        """

        helper.install(node, 'sdns')

        cert_path, key_path = self._getCryptoPaths()


        # use MiniCA root certificate which is installed in every host's trust store
        # as rhine certificate to verify RHINE records
        rcert = '/usr/local/share/ca-certificates/SEEDEMU_Internal_Root_CA.crt'

        # on which address the resolver listens for requests
        bind_addrport = self.bindDo53AddrPort() # from local-host
        bind_scion_doq = '' if not self.getIsPublicResolver() else f'bindsdoq="{self.bindDoQAddrPort(node)}"' # from clients

        '''
        root_ns = [ r.split('=')[1].strip('"') for r in self.getRootServers() if 'TXT' in r]
        sc_root_hints = ',\n'.join( map( lambda x: f'"{x}:{port}"', root_ns))
        sdns_conf = DomainNameCachingServiceFileTemplates['sdns_conf'].format(rhine_cert=rcert,
                                                                              bindsdoq=bind_scion_doq,
                                                                              bind_addr_port=bind_addrport,
                                                                              cert_path=cert_path,
                                                                              key_path=key_path,
                                                                              scion_root_hints=sc_root_hints)
        '''
        root_ns = [ (r.split('TXT')[0].strip() ,r.split('=')[1].strip('"')) for r in self.getRootServers() if 'TXT' in r]
        named_sc_root_hints = ',\n'.join( map( lambda x: f'["{x[1]}:{self.__doq_port}", "{x[0]}"]', root_ns))
        sdns_conf = DomainNameCachingServiceFileTemplates['sdns_conf_new'].format(rhine_cert=rcert,
                                                                              bindsdoq=bind_scion_doq,
                                                                              bind_addr_port=bind_addrport,
                                                                              cert_path=cert_path,
                                                                              key_path=key_path,
                                                                              scion_root_hints=named_sc_root_hints)


        node.setFile('/etc/sdns/sdns.conf', sdns_conf)

        # start sdns process
        node.addSoftware('apache2-utils') # for rotatelogs
        # sdns needs scion paths for root server update on startup
        node.appendStartCommand('sleep 20; sdns --config /etc/sdns/sdns.conf 2>&1 | rotatelogs -n 2 /var/log/sdns.log 1M', fork=True)


    def _do_install_bind9(self, node: Node):
        node.addSoftware('bind9')
        node.setFile('/etc/bind/named.conf.options',
                      DomainNameCachingServiceFileTemplates['named_options'])
        node.setFile('/etc/bind/named.conf.local', '')
        if len(self.getRootServers()) > 0:
            hint = '\n'.join(self.getRootServers())
            node.setFile('/usr/share/dns/root.hints', hint)
            node.setFile('/etc/bind/db.root', hint)
        node.appendStartCommand('service named start')

        for (zone_name, vnode_name) in self.__pending_forward_zones.items():
            pnode = self.__emulator.resolvVnode(vnode_name)

            ifaces = pnode.getInterfaces()
            assert len(ifaces) > 0, 'resolvePendingRecords(): node as{}/{} has no interfaces'.format(pnode.getAsn(), pnode.getName())
            assert len(ifaces) == 1, f'Node {pnode.getName()} is not a host'
            vnode_addr = ifaces[0].getAddress()
            node.appendFile('/etc/bind/named.conf.local',
                        'zone "{}" {{ type forward; forwarders {{ {}; }}; }};\n'.format(zone_name, vnode_addr))

        if not self.__configure_resolvconf: return
        self._configure_resolvconf_impl(node)


    def _configure_resolvconf_impl(self, node: Node):
        """ resolv.conf of all other nodes in the node's AS will be set to this server/node.
        """

        reg = self.__emulator.getRegistry()
        (scope, _, _) = node.getRegistryInfo()
        sr = ScopedRegistry(scope, reg)
        addr = getNodeAddr(node)

        for rnode in sr.getByType('rnode'):
            rnode.appendFile('/etc/resolv.conf.new', 'nameserver {}\n'.format(addr))
            if 'cat /etc/resolv.conf.new > /etc/resolv.conf' not in rnode.getStartCommands():
                rnode.appendStartCommand('cat /etc/resolv.conf.new > /etc/resolv.conf')

        for hnode in sr.getByType('hnode'):
            if 'cat /etc/resolv.conf.new > /etc/resolv.conf' not in hnode.getStartCommands():
                hnode.appendStartCommand('cat /etc/resolv.conf.new > /etc/resolv.conf')
            hnode.appendFile('/etc/resolv.conf.new', 'nameserver {}\n'.format(addr))

class DomainNameCachingService(Service):
    """!
    @brief Caching DNS (i.e., Local DNS)

    @todo DNSSEC, DoE
    """

    __auto_root: bool
    __do_enc: bool
    __wipe_docker_resolv_conf: bool
    # TODO: maybe we should distinguish whether to wipe the client-host's /etc/resolv.conf
    #       or the node's which have a CachingServer installed or both ..

    @classmethod
    def getAvailableOptions(cls):
        # avoid code duplication and have DNS options only in one place
        return DomainNameService.getAvailableOptions()

    def _doInstall(self, node: Node, server: DomainNameCachingServer):
        opt = node.getOption('dns_setup')
        if opt == None:
            for o in self.getAvailableOptions():
                node.setOption(o)
        server.install(node)# pass self like with DomainNameServers ?!

    def setConfigureFallbackResolvconf(self, configure: bool):
        """
        shall the /etc/resolv.conf files of all hosts that don't fall
        into the catchment of any CachingResolver be configured to use
        all resolvers or not.
        The default is false, and these 'leftover' nodes
        just have any resolvers configured.
        """
        self.__configure_fallback_resolveconf = configure

    def __init__(self, autoRoot: bool = True,
                 do_enc: bool = False,
                 wipe_docker_resolv_conf: bool = False):
        """!
        @brief DomainNameCachingService constructor.

        @param autoRoot (optional) find root zone name servers automatically.
        True by default, if true, DomainNameCachingService will find root NS in
        DomainNameService and use them as root.
        @param do_enc  support encrypted DNS (DNS privacy)
        @param wipe_docker_resolve_conf whether the default docker /etc/resolv.conf config
                    shall be kept or overridden
        """
        super().__init__()
        self.__configure_fallback_resolveconf = False
        self.__auto_root = autoRoot
        self.__wipe_docker_resolv_conf = wipe_docker_resolv_conf
        self.__do_enc = do_enc
        self.addDependency('Base', False, False)
        if autoRoot:
            self.addDependency('DomainNameService', False, False)


    def _createServer(self) -> DomainNameCachingServer:
        return DomainNameCachingServer(self.__do_enc,
                                       wipe_docker_resolv_conf=self.__wipe_docker_resolv_conf)

    def getName(self) -> str:
        return 'DomainNameCachingService'

    def getConflicts(self) -> List[str]:
        return ['DomainNameService']

    def configure(self, emulator: Emulator):
        super().configure(emulator)
        targets = self.getTargets()
        if self.__auto_root:
            dns_layer: DomainNameService = emulator.getRegistry().get('seedemu', 'layer', 'DomainNameService')
            root_zone = dns_layer.getRootZone()
            root_servers = root_zone.getGuleRecords()
            for (server, node) in targets:
                server.setRootServers(root_servers)

        addrs = []
        for (server, node) in targets:
            server.configure(emulator, node)

            address = getNodeAddr(node)
            assert address != "", 'address is not configured.'
            addrs.append((address, server))

        # NOTE this is no duplication with CachingServer::_configure_resolvconf_impl !
        if self.__configure_fallback_resolveconf:
            self._init_etc_resolv_conf(addrs, emulator)


    def _init_etc_resolv_conf(self, addrs: List[Tuple[str,Server]], emulator: Emulator):
        """
        @param addrs IP/SCION addresses of nameservers.
                    They will be added as nameserver in /etc/resolv.conf
        @note call only after CachingServers have been configured
        """
        #The implementation in CachingServer adds resolvers to only hosts which are inside of their catchment
        # this method is a fallback for all nodes which aren't in any catchment (of at least one resolver)

        # For the nodes that are not covered, all the local DNS servers will be added to them (the default behavior).
        reg = emulator.getRegistry()
        for ((scope, type, name), node) in reg.getAll().items():
            if type in ['hnode', 'rnode']:
                if not any(command[0] == ': > /etc/resolv.conf' for command in node.getStartCommands()):
                    node.insertStartCommand(0,': > /etc/resolv.conf')
                    for a, s in (addrs):
                        #if s.getIsNodeWithinCatchment(node):
                            node.insertStartCommand(1, 'echo "nameserver {}" >> /etc/resolv.conf'.format(a))

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'DomainNameCachingService:\n'

        indent += 4

        out += ' ' * indent
        out += 'Configure root hint: {}\n'.format(self.__auto_root)

        return out