
from .Service import Server, Service
from .Node import Node
from .Binding import Filter
from typing import List, Iterable
from .Emulator import Emulator
from enum import Enum
import re
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)



def ipsInNetwork(ips: Iterable, network: str) -> bool:
    """!
    @brief Check if any of the IPs in the iterable is in the network.
    This function supports both IPv4 and IPv6 via IPv4-Mapped IPv6 Address.

    @param ips The iterable of IPs.

    @param network The network.

    @returns True if any of the IPs is in the network, False otherwise.
    """
    net = ip_network(network)
    map6to4 = int(IPv6Address("::ffff:0:0"))
    if isinstance(net, IPv4Network):
        net = IPv6Network(
            # convert to IPv4-Mapped IPv6 Address for computation
            #   ::ffff:V4ADDR
            # 80 + 16 +  32
            # https://datatracker.ietf.org/doc/html/rfc4291#section-2.5.5.2
            f"{IPv6Address(map6to4 | int(net.network_address))}/{96 + net.prefixlen}"
        )
    for ip in ips:
        ip = ip_address(ip)
        if isinstance(ip, IPv4Address):
            ip = IPv6Address(map6to4 | int(ip))
        if ip in net:
            return True
    return False


class CaAlgorithm(Enum):
    ECDSASHA256 = 0
    ECDSASHA384 = 1
    ED25519 = 2

class RootCAStoreBase:
    """
    common base interface for any means that can be used
    to generate and issue cryptografic certificates

    @details can be implemented i.e. with SmallstepCA, OpenSSL or MiniCA
    """

    def __init__(self, caDomain: str = "ca.internal", algotype: CaAlgorithm = CaAlgorithm.ECDSASHA256):
        """!
        @brief Create a new RootCAStore.        
        @param caDomain The domain name of the CA.
        @param algotype which algorithm to use for asymmetric cryptography
                Attention: The default is reasonable i.e. browsers dont support Ed25519 (as of 2025)
                 so you better leave it alone unless you know exactly why you need sth. else.
        """
        self._algo = algotype
        self._caDomain = caDomain

    def algorithm(self) -> CaAlgorithm:
        return self._algo

    def domain(self) -> str:
        return self._caDomain

    def getStorePath(self) -> str:
        pass
    def setPassword(self, password: str) -> 'RootCAStoreBase':
        pass
    def getPassword(self) -> str:
        pass
    def setRootCertAndKey(self, rootCertPath: str, rootKeyPath: str) -> 'RootCAStoreBase':
        pass

    def initialize(self):
        pass

    def generateCert(self, server_names: List[str]):
        """
        generates a key pair and certificate for the given domain/s
        @details called by CAServers to implement their client's CertRequests
        @note implementation should be idempotent i.e. when called the second time
            returns the existing cert for the domain name,
            rather than generating a new one (and overriding the existing one)
        """
        pass

    def save(self, path: str):
        pass
    def restore(self, path: str):
        pass

class CAServerBase(Server):
    """
    a CA Server is a means for other (i.e. Web-) Servers
    to obtain a certificate for their domain-name.
    This is required to serve clients over HTTPS.
    """
    def __init__(self):
        super().__init__()
        self.__filters: List[Filter | None] = []
        self.__duration = "2160h"
        self.__id: int = None
        self.__ca_store = None
        self.__ca_domain = None

    def getCAStore(self) -> RootCAStoreBase:
        return self.__ca_store

    def serverID(self) -> int:
        return self.__id

    def getCADomain(self) -> str:
        """
        returns the domain name of the certificate authority
        whoose root certificate is required to verify certificates
        issued by this CAServer.
        @note depends on the RootCAStore used by this Server
        """
        return self.__ca_domain

    def certDuration(self) -> str:
        """
        returns how long certificates issued by this server
        will be valid
        """
        return self.__duration

    def _appendFilter(self, filter: Filter):
        self.__filters.append(filter)

    def setCertDuration(self, duration: str) -> 'CAServerBase':
        """!
        @brief Set the certificate duration.

        @param duration. For example, '24h', '48h', '720h'. The duration must no less than 12h.
        Default is '2160h' (90 days).

        @returns self, for chaining API calls.
        """
        if not duration.endswith("h"):
            raise ValueError('The duration must end with "h".')
        if int(duration.rstrip("h")) < 12:
            raise ValueError("The duration must no less than 12h.")
        self.__duration = duration
        return self

    def installCACert(self, filter: Filter = None) -> 'CAServerBase':
        """!
        @brief Install the CA certificate to the nodes that match the filter.
        Calling these function multiple times will not override the previous filter.
        ```
        caServer.installCACert(Filter(asn=150))
        caServer.installCACert(Filter(asn=151))
        # The above code will install the CA certificate to all nodes in ASN 150 and 151.
        ```

        @param filter The filter to match the nodes. Default is None, which means all nodes.

        @returns self, for chaining API calls.
        """
        # This is possible to do it in runtime
        if filter:
            assert (
                not filter.allowBound
            ), "allowBound filter is not supported in the global layer."
        self._appendFilter(filter)
        return self


    def enableHTTPSFunc(self, context: str, node: Node, server_names: List[str],
                        dst_cert_path: str = None, dst_key_path: str = None,
                        update: bool = True):
        """
        a callback that web servers can invoke to equip themselves with a TLS certificate
        issued by this CAServer
        @param dst_cert_path path and filename where to place the requested certificate onto 'node'
              Some CA service implementations might not require this argument or ignore it.
        @param dst_key_path path and filename where to place the web servers private key corresponding to the certificate.
        @param node onto which the web server is installed and whose filesystem must contain the servers certificate
        @param update whether to call 'update-ca-certificates
        """

    def _installRootCertToClient(self, node: Node):
        """
        install the root certifiate from the CAStore into the client node's trust store
        so it can verify certificates issued by the CA
        """
        raise NotImplemented

    def setCAStore(self, caStore: RootCAStoreBase) -> 'CAServerBase':
        """
        """
        self.__ca_store = caStore
        self.__ca_store.initialize()
        self.__ca_domain = self.__ca_store._caDomain
        return self

    def _serverConfigure(self, id: int, all_nodes: List[Node]):
        """
        @param id ID of the CAServer
        @param all_nodes target hosts where to install the root certificates
                of the CAServer with the given ID
        """
        # Install the CA certificate to the nodes
        self.__id = id
        if None in self.__filters:
            self.__filters = [None]
        all_nodes_dict = {node: False for node in all_nodes}
        for filter in self.__filters:
            for node in all_nodes:
                if all_nodes_dict[node]:
                    continue
                if filter:
                    if filter.asn and filter.asn != node.getAsn():
                        continue
                    if filter.nodeName and not re.compile(filter.nodeName).match(
                        node.getName()
                    ):
                        continue
                    if filter.ip and filter.ip not in map(
                        lambda x: x.getAddress(), node.getInterfaces()
                    ):
                        continue
                    if filter.prefix:
                        ips = {
                            host
                            for host in map(
                                lambda x: x.getAddress(), node.getInterfaces()
                            )
                        }
                        if not ipsInNetwork(ips, filter.prefix):
                            continue
                    if filter.custom and not filter.custom(node.getName(), node):
                        continue
                self._installRootCertToClient(node)
                all_nodes_dict[node] = True



class CAServiceBase(Service):

    def __init__(self):

        super().__init__()
        self.addDependency("Routing", False, False)
        self.addDependency("DomainNameService", False, True)
        self.addDependency("EtcHost", False, True)
        self._caServers: List[CAServerBase] = []

    def _createServer(self) -> Server:
        raise NotImplemented

    def getName(self):
        return "CertificateAuthority"

    def addCAServer(self, server: CAServerBase) -> 'CAServiceBase':
        # FIXME i think this is redundant with Service::getPendingTargets ?!
        self._caServers.append(server)
        return self

    def configureCAClient(self, node: Node) -> 'CAServiceBase':
        """
        called on all clients of the CA in the course of configure()
        """
        return self

    def configureCAServer(self, server_id: int, caServer: CAServerBase, all_nodes: List[Node]) -> 'CAServiceBase':
        """
        invoked for every caServer of this service
        @param all_nodes  all (potential) clients  of the CAServer (endhosts)
        """
        caServer._serverConfigure(server_id, all_nodes)

    def configure(self, emulator: Emulator):
        """
        configures all CA clients and CAServers
        """
        super().configure(emulator)
        all_nodes_items = emulator.getRegistry().getAll().items()
        all_nodes: List[Node] = []
        for (_, type, _), obj in all_nodes_items:
            if type not in ["rs", "rnode", "hnode", "csnode"]:
                continue
            all_nodes.append(obj)

        for node in all_nodes:
            self.configureCAClient(node)

        for id, caServer in enumerate(self._caServers):
            self.configureCAServer(id, caServer, all_nodes)

