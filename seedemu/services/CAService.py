from __future__ import annotations
from contextlib import contextmanager
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)
import os
import re
import secrets
import shutil
import string
import subprocess
import tempfile
from typing import Dict, TYPE_CHECKING, Iterable, List

from seedemu.core.Emulator import Emulator
from seedemu.utilities import BuildtimeDockerImage, BuildtimeDockerFile

if TYPE_CHECKING:
    from seedemu.services.WebService import WebServer
    from seedemu.core import Node, Filter
from seedemu.core import Service, Server

CaFileTemplates: Dict[str, str] = {}

CaFileTemplates["certbot_renew_cron"] = """\
# /etc/cron.d/certbot: crontab entries for the certbot package
#
# Upstream recommends attempting renewal
#
# Eventually, this will be an opportunity to validate certificates
# haven't been revoked, etc.  Renewal will only occur if expiration
# is within 8 hours.
#
# Important Note!  This cronjob will NOT be executed if you are
# running systemd as your init system.  If you are running systemd,
# the cronjob.timer function takes precedence over this cronjob.  For
# more details, see the systemd.timer manpage, or use systemctl show
# certbot.timer.
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

* */1 * * * root test -x /usr/bin/certbot -a \! -d /run/systemd/system && perl -e 'sleep int(rand(3600))' && REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt certbot -q renew
"""

CaFileTemplates['minica_docker'] = """\
FROM golang:1.24
WORKDIR /
RUN apt-get update && apt-get install -y git
RUN git clone https://github.com/jsha/minica.git
RUN cd minica && go build .
RUN cd minica && go install .
RUN mkdir /certs
WORKDIR /certs
"""

'''
# Generate a root key and cert in minica-key.pem, and minica.pem,
#  then generate and sign an end-entity key and cert, storing them in ./foo.com/
$ minica --domains foo.com

# Wildcard
$ minica --domains '*.foo.com'
'''

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


class CAServerBase(Server):

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
        return self.__ca_domain

    def certDuration(self) -> str:
        return self.__duration

    def _appendFilter(self, filter: Filter):
        self.__filters.append(filter)

    def setCertDuration(self, duration: str) -> CAServerBase:
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

    def installCACert(self, filter: Filter = None) -> CAServerBase:
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


    def enableHTTPSFunc(self, node: Node, server_names: List[str], dst_cert_path: str = None, dst_key_path: str = None):
        """
        a callback that web servers can invoke to equip themselves with a TLS certificate
        issued by this CAServer
        @param dst_cert_path path and filename where to place the requested certificate onto 'node'
              Some CA service implementations might not require this argument or ignore it.
        @param dst_key_path path and filename where to place the web servers private key corresponding to the certificate.
        @param node onto which the web server is installed and whose filesystem must contain the servers certificate
        """

    def _installRootCertToClient(self, node: Node):
        """
        install the root certifiate from the CAStore into the client node's trust store
        so it can verify certificates issued by the CA
        """
        raise NotImplemented

    def setCAStore(self, caStore: RootCAStoreBase) -> CAServerBase:
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

    def addCAServer(self, server: CAServerBase) ->CAServiceBase:
        # FIXME i think this is redundant with Service::getPendingTargets ?!
        self._caServers.append(server)
        return self

    def configureCAClient(self, node: Node) -> CAServiceBase:
        """
        called on all clients of the CA in the course of configure()
        """
        return self

    def configureCAServer(self, server_id: int, caServer: CAServerBase, all_nodes: List[Node]) -> CAServiceBase:
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

class RootCAStoreBase:

    def __init__(self, caDomain: str = "ca.internal"):
        """!
        @brief Create a new RootCAStore.

        @param caDomain The domain name of the CA.
        """
        self._caDomain = caDomain

    def domain(self) -> str:
        return self._caDomain

    def getStorePath(self) -> str:
        pass
    def setPassword(self, password: str) -> RootCAStoreBase:
        pass
    def getPassword(self) -> str:
        pass
    def setRootCertAndKey(self, rootCertPath: str, rootKeyPath: str) -> RootCAStoreBase:
        pass

    def initialize(self):
        pass

    def save(self, path: str):
        pass
    def restore(self, path: str):
        pass


class RootMiniCAStore(RootCAStoreBase):

    def __init__(self, caDomain: str):
        super().__init__(caDomain)

        self._dockerfile_contents = CaFileTemplates['minica_docker']

        #self._minica_image = BuildtimeDockerFile("minica") #.build(self.dockerfile_contents).container()
        self.__caDir = tempfile.mkdtemp(prefix="seedemu-minica-")

        with cd(self.__caDir):
            self.__container = BuildtimeDockerImage("minica").build(BuildtimeDockerFile(self._dockerfile_contents)).container()
            self.__container.user(f"{os.getuid()}:{os.getuid()}").mountVolume( self.__caDir, "/certs" )#.entrypoint("step")
            # .user(f"{os.getuid()}:{os.getuid()}")


    def generateCert(self, server_names: List[str]):
        """
        generates a key pair and certificate for the given domain
        """
        self.__container.run(f'minica --domains { ' '.join(server_names)}') # cert & key is output to ./{domain.name}/


    def getStorePath(self) -> str:
        """!
        @brief Get the path of the CA store on the docker host.
        """
        return self.__caDir

    def initialize(self):
        """!
        @brief Initialize the CA store.
        User can either call it manually or let the CA server to call it.
        """
        '''
        if self.__initialized:
            return
        with cd(self.__caDir):
            initialize_command = "minica --domains '*'"
            self.__container.run(initialize_command)

        self.__initialized = True
        '''




class MiniCAServer(CAServerBase):


    def __init__(self):
        super().__init__()

    def getName(self):
        return "MinicaCertificateAuthority"

    def install(self, node: Node):
        """!
        @brief Install the CA Server on the node.
        @note does nothing - thats the crux of MiniCAService:
                To do everything at build time !
                MiniCAservers do not exist at runtime.
        """
        return


    def _installRootCertToClient(self, node):
        """
        install the root certifiate from the CAStore into the client node's trust store
        so it can verify certificates issued by the CA
        """
        node.addSoftware("ca-certificates")

        node.importFile(
            os.path.join(
                self.getCAStore().getStorePath(), "minica.pem"
            ),
            f"/usr/local/share/ca-certificates/SEEDEMU_Internal_Root_CA.pem",
        )

        node.appendStartCommand("update-ca-certificates")





    def enableHTTPSFunc(self, node: Node, server_names: List[str], dst_cert_path: str, dst_key_path: str):
        """
        unlike StepCA requires no ACME at runtime,
        because it copies all required stuff into containers at build time
        @param node  the Node onto which the (Web/Dns whatever)Server which requires TLS is installed
        @param server_name domain-name of the Server for which it needs a certificate
        @param dst_cert_path destination path on 'node' where to place the generated cert and key
        """

        store: RootMiniCAStore = self.getCAStore()
        assert isinstance(store, RootMiniCAStore), 'logic error'
        store.generateCert(server_names)

        # TODO copy generated certs from caDir to node

        cert_dir = os.path.join(store.getStorePath(), server_names[0])
        for root, _, files in os.walk(cert_dir):
            for file in files:
                node.importFile(
                    os.path.join(root, file),
                    dst_cert_path)
                '''
                os.path.join(
                    "/root",
                    os.path.relpath(os.path.join(root, file), store.getStorePath()),
                ),
                '''




        node.addSoftware("ca-certificates")
        node.appendStartCommand("update-ca-certificates")

class MiniCAService(CAServiceBase):

    def _createServer(self) -> Server:
        server = MiniCAServer()
        self.addCAServer(server)
        return server





class StepCAServer(CAServerBase):

    def __init__(self, step_version: str):
        super().__init__()
        self._step_version = step_version


    def _installRootCertToClient(self, node):
        """
        copy the root certificate of this CAServer's RootCAStore to the client 'node'
        so it can verify certificates issued by this CAServer
        """
        node.addSoftware("ca-certificates")
        node.importFile(
            os.path.join(
                self.getCAStore().getStorePath(), ".step/certs/root_ca.crt"
            ),
            f"/usr/local/share/ca-certificates/SEEDEMU_Internal_Root_CA_{self.serverID()}.crt",
        )
        node.appendStartCommand("update-ca-certificates")


    def enableHTTPSFunc(self, node: Node, server_names: List[str], dst_cert_path: str = None, dst_key_path:str = None):
        """!
        @brief Enable HTTPS for the web server.
        This is not supposed to be called directly. The WebService will call this function.

        @param node The node to enable HTTPS.

        @param web The web server to enable HTTPS.
        """
        node.addSoftware("certbot").addSoftware("python3-certbot-nginx").addSoftware(
            "cron"
        )
        # wait for the name server
        node.setFile("/etc/cron.d/certbot", CaFileTemplates["certbot_renew_cron"])
        node.appendStartCommand(
            'until curl --silent https://{}/acme/acme/directory > /dev/null ; do echo "Network retry in 2 s" && sleep 2; done'.format(
                self.getCADomain()
            )
        )
        node.appendStartCommand(
            'REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
certbot --server https://{ca_domain}/acme/acme/directory --non-interactive --nginx --no-redirect --agree-tos --email example@example.com \
-d {server_name} > /dev/null && echo "ACME: cert issued"'.format(
                server_name=" -d ".join(server_names), ca_domain=self.getCADomain()
            )
        )
        node.appendStartCommand(
            "sed 's/^#\? \?renew_before_expiry = .*$/renew_before_expiry = 8hours/' -i /etc/letsencrypt/renewal/*.conf"
        )
        node.appendStartCommand("crontab /etc/cron.d/certbot && service cron start")



    def install(self, node: Node):
        """!
        @brief Install the CA Server on the node.
        """
        node.addSoftware("ca-certificates")
        node.addBuildCommand(
            f"\
if uname -m | grep x86_64 > /dev/null; then \
curl -O -L https://github.com/smallstep/certificates/releases/download/v{self._step_version}/step-ca_{self._step_version}_amd64.deb && \
apt install -y ./step-ca_{self._step_version}_amd64.deb; \
else \
curl -O -L https://github.com/smallstep/certificates/releases/download/v{self._step_version}/step-ca_{self._step_version}_arm64.deb && \
apt install -y ./step-ca_{self._step_version}_arm64.deb; \
fi"
        )
        self.__caDir = self.getCAStore().getStorePath()
        for root, _, files in os.walk(self.__caDir):
            for file in files:
                node.importFile(
                    os.path.join(root, file),
                    os.path.join(
                        "/root",
                        os.path.relpath(os.path.join(root, file), self.__caDir),
                    ),
                )
        node.appendStartCommand(
            f"cp $(step path)/certs/root_ca.crt /usr/local/share/ca-certificates/SEEDEMU_Internal_Root_CA_{self.serverID()}.crt && \
update-ca-certificates"
        )
        node.appendStartCommand(
            f"jq '.authority.claims.defaultTLSCertDuration |= \"{self.certDuration()}\"' $(step path)/config/ca.json > $(step path)/config/ca.json.tmp && mv $(step path)/config/ca.json.tmp $(step path)/config/ca.json"
        )
        node.appendStartCommand(
            "step-ca --password-file /root/password.txt $(step path)/config/ca.json > /var/step-ca.log 2> /var/step-ca.log",
            fork=True,
        )

class StepCAService(CAServiceBase):
    """!
    @brief The Certificate Authority (CA) service.

    This service helps setting up a Certificate Authority (CA). It works by
    generating a self-signed root certificate and then signing the server
    certificate with the root certificate.
    """

    def __init__(self):
        """!
        @brief create a new CA service which will setup the PKI infrastructure.

        @param caStore The RootCAStore object.
        """
        super().__init__()

        self._step_version = self._preset_step_version()

    def getName(self):
        return "SmallstepCertificateAuthority"

    @classmethod
    def _preset_step_version(cls):
        return "0.26.1"

    def configureCAClient(self, node):

            node.addBuildCommand(
                f"\
if uname -m | grep x86_64 > /dev/null; then \
curl -O -L https://github.com/smallstep/cli/releases/download/v{self._step_version}/step-cli_{self._step_version}_amd64.deb && \
apt install -y ./step-cli_{self._step_version}_amd64.deb; \
else \
curl -O -L https://github.com/smallstep/cli/releases/download/v{self._step_version}/step-cli_{self._step_version}_arm64.deb && \
apt install -y ./step-cli_{self._step_version}_arm64.deb; \
fi"
            )
            return self

    def _createServer(self) -> Server:
        server = StepCAServer(self._step_version)
        self.addCAServer(server)
        return server




@contextmanager
def cd(path):
    """@private Not supposed to be imported. Any other module should not rely on this function."""
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


def sh(command, input=None):
    """@private Not supposed to be imported. Any other module should not rely on this function."""
    try:
        if isinstance(command, list):
            command = " ".join(command)
        p = subprocess.run(
            command,
            shell=True,
            input=input,
        )
        return p.returncode
    except subprocess.CalledProcessError as e:
        return e.returncode



class RootStepCAStore(RootCAStoreBase):
    """
    initializes a smallstep-cli ca in a buildtime docker container
    and makes the generated root certificates accessible on the docker host
    via  /tmp/seedemu-ca bind mount
    """
    def __init__(self, caDomain: str = "ca.internal"):
        """!
        @brief Create a new RootCAStore.

        @param caDomain The domain name of the CA.
        """
        super().__init__(caDomain)
        self.__initialized = False
        self.__caDir = tempfile.mkdtemp(prefix="seedemu-ca-")
        self.setPassword( "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(64)
        ))

        self.__pendingRootCertAndKey = None
        with cd(self.__caDir):
            self.__container = BuildtimeDockerImage(
                f"smallstep/step-cli:{StepCAService._preset_step_version()}"
            ).container()
            self.__container.user(f"{os.getuid()}:{os.getuid()}").mountVolume(
                self.__caDir, "/root"
            ).env("STEPPATH", "/root/.step").entrypoint("step")

    def getStorePath(self) -> str:
        """!
        @brief Get the path of the CA store.

        @returns The path of the CA store.
        """
        return self.__caDir

    def setPassword(self, password: str) -> RootStepCAStore:
        """!
        @brief Set the password to decrypt the CA Key if it is provided, otherwise, the password is used to encrypt the CA Key.
        It must be called before the CA store is initialized.

        @param password The password to encrypt/decrypt the CA Key.

        @returns self, for chaining API calls.
        """
        if self.__initialized:
            raise RuntimeError("The CA store is already initialized.")
        self.__password = password
        return self

    def getPassword(self) -> str:
        return self.__password

    def setRootCertAndKey(self, rootCertPath: str, rootKeyPath: str) -> RootStepCAStore:
        """!
        @brief Set the root certificate and key for the CA.
        It must be called before the CA store is initialized.

        @param rootCertPath The path to the root certificate.

        @param rootKeyPath The path to the root key.

        @return self, for chaining API calls.
        """
        if self.__initialized:
            raise RuntimeError("The CA store is already initialized.")
        with cd(self.__caDir):
            shutil.copyfile(rootCertPath, "root_ca.crt")
            shutil.copyfile(rootKeyPath, "root_ca_key")
        self.__pendingRootCertAndKey = (
            f"{self.__caDir}/root_ca.crt",
            f"{self.__caDir}/root_ca_key",
        )
        return self

    def initialize(self):
        """!
        @brief Initialize the CA store.
        User can either call it manually or let the CA server to call it.
        """
        if self.__initialized:
            return
        with cd(self.__caDir):
            with open("password.txt", "w") as f:
                f.write(self.getPassword())
            initialize_command = "ca init"
            if self.__pendingRootCertAndKey:
                initialize_command += (
                    " --root /root/root_ca.crt --key /root/root_ca_key"
                )
            initialize_command += f' --deployment-type "standalone" --name "SEEDEMU Internal" \
--dns "{self.domain()}" --address ":443" --provisioner "admin" --with-ca-url "https://{self.domain()}" \
--password-file /root/password.txt --provisioner-password-file /root/password.txt --acme'
            self.__container.run(initialize_command)

        self.__initialized = True

    def save(self, path: str):
        """!
        @brief Save the CA store to a directory.
        It must be called after the CA store is initialized.

        @param path The path to save the CA store.
        """
        if not self.__initialized:
            raise RuntimeError("The CA store is not initialized.")
        shutil.copytree(self.__caDir, path)

    def restore(self, path: str):
        """!
        @brief Restore the CA store from a directory.
        It must be called before the CA store is initialized.

        @param path The path to restore the CA store from.
        """
        if self.__initialized:
            raise RuntimeError("The CA store is already initialized.")
        shutil.copytree(path, self.__caDir)
        self.__initialized = True
