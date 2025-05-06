from seedemu.core import Node, Option
from enum import Enum
from dataclasses import dataclass
from random import randint
import os
from typing import List
from seedemu.utilities.BuildtimeDocker import BuildtimeDockerFile, BuildtimeDockerImage

_default_name = '@'

def rrname2Type(rrtype: str):
    match rrtype:
        case 'A':
            return A_RR
        case 'NS':
            return NS_RR
        case 'SOA':
            return SOA_RR
        case 'TXT':
            return TXT_RR

@dataclass
class ResourceRecord:
    # TODO: maybe move the 'name' here . .
    #       default value could be '@'
    #ttl: int = 9999999
    # class: str = 'IN' #internet
    # type
    pass

@dataclass
class A_RR(ResourceRecord):
    """Maps a domain name to a single IPv4 address
    """
    address: str # an IPv4 or IPv6 address
    name: str = _default_name # fqn whose address is given by this record (zonename)
    # length: int = 4
    def __str__(self):
        return f'{self.name} A {self.address}'

@dataclass
class NS_RR(ResourceRecord):
    """Names a name server (NS) (or DNS server) for a zone"""
    nsname: str # names the authoritative nameserver
    zonename: str = _default_name # names the domain/zone
    def __str__(self):
        return f'{self.zonename} NS {self.nsname}'

@dataclass
class SOA_RR(ResourceRecord):
    """SOA (start of authority) Provides parameters for a zone"""
    mname: str
    rname: str
    zonename: str = _default_name
    serial: int = randint(1, 0xffffffff)
    refresh: int = 86400
    retry: int = 7200
    expire: int = 3600000
    minimum: int = 3600

    def __str__(self):
        return f'{self.zonename} SOA {self.mname} {self.rname} {self.serial} {self.refresh} {self.retry} {self.expire} {self.minimum}'


        #'@ SOA {} {} {} 900 900 1800 60'.format( f'ns1.{zonename}', # MNAME ?!
        #                                            f'admin.{zonename}', # RNAME ?!
        #                                            randint(1, 0xffffffff) #SERIAL?!
        #                                            )


'''
CNAME (alias) Maps a domain name (the alias) to another
domain name (the canonical name)
'''
# CNAME

# PTR

@dataclass
class TXT_RR(ResourceRecord):
    """
    i.e.:      perrig.inf.ethz.ch. 273 IN TXT "scion=17-ffaa:0:1102,129.132.121.164"
    """

    text: str # i.e. a SCION-RR
    name: str = _default_name# domainname for which this TXT record is
    def __str__(self):
        #return f'{self.name} {self.ttl} {self.text}'
        return f'{self.name} TXT "{self.text}"'

#ORIGIN


class DNSStackHelperBase:
    """"""
    def install(self, node: Node, context: str):
        pass

class DNSStackHelper(DNSStackHelperBase):
    """installs CoreDNS nameserver and sdns resolver onto nodes.
        As well as the exdns 'dig' like CLI query tool.
    """

    __seen_nodes: List[Node] = []
    # target-name, url, branch, checkout-dir, do-build
    __dns_urls = [('dns', 'https://github.com/netsys-lab/dns', 'master-rebase', '/repos/dns', False),
                  ('coredns', 'https://github.com/netsys-lab/scion-coredns-doq', 'attempt-rebase', '/repos/coredns', True),
                  ('sdns', 'https://github.com/netsys-lab/scion-sdns', 'new-main', '/repos/sdns', True),
                  ('exdns', 'https://github.com/netsys-lab/exdns', 'master-rebased', '/repos/exdns', True)
                ]

    def getGoBuildImage(self):
        return 'golang:1.24-alpine'

    def __init__(self):
        # create buildtime docker container

        #out = 'coredns' # one of 'dns' 'coredns' 'sdns' 'exdns'
        #build_path = f".dns_build_output/{out}"
        DNSStackHelper.build_path = ".dns_build_output"

        if not os.path.isdir(DNSStackHelper.build_path):

            DNS_BUILD_TEMPLATE = f"""FROM {self.getGoBuildImage()}
            RUN apk add --no-cache git
            """

            for target in DNSStackHelper.__dns_urls:
                DNS_BUILD_TEMPLATE += f'RUN git clone --branch {target[2]} {target[1]} {target[3]}\n'
                if target[4]:
                    if target[0] == 'exdns':
                        DNS_BUILD_TEMPLATE += f'RUN cd {target[3]}/q && go mod tidy && go build -o ../bin/{target[0]} .\n'
                    else:
                        DNS_BUILD_TEMPLATE += f'RUN cd {target[3]} && go mod tidy && go build -o bin/{target[0]} .\n'


            DNSStackHelper.dockerfile = BuildtimeDockerFile(DNS_BUILD_TEMPLATE)
            DNSStackHelper.container = BuildtimeDockerImage(f"dns-build-container").build(DNSStackHelper.dockerfile).container()


        #else:
        #    output_dir = os.path.join(os.getcwd(), build_path)
        #    return output_dir

            # TODO: copy binaries from BuildtimeDockerContainer mount to node's container image
            current_dir = os.getcwd()
            output_dir = os.path.join(current_dir, DNSStackHelper.build_path)
            # copy from build container to docker host
            copy_command = []
            for target in DNSStackHelper.__dns_urls:
                if target[4]:
                    copy_command.append(f"cp -r {target[3]}/bin/* /build")

            full_cp_cmd = f"-c \"{' && '.join(copy_command)}\""
            DNSStackHelper.container.entrypoint("sh").mountVolume(output_dir, "/build").run(
               full_cp_cmd
            )
            #return output_dir

            DNSStackHelper.out_dir = output_dir

    def install(self, node: Node, context: str):
        """
        @param context what should be installed on 'node'
                i.e. 'coredns' (nameserver) or 'sdns' (resolver)
        """
        if node not in DNSStackHelper.__seen_nodes:
            DNSStackHelper.__seen_nodes.append(node)
            path_to_binaries = "/bin/dns"
            node.addSharedFolder(path_to_binaries, DNSStackHelper.out_dir)
            node.addDockerCommand(f'ENV PATH={path_to_binaries}:$PATH ')


class DNSStack(Enum):
    """
    user choice whether the naming system in the emulation
    shall support Next-Gen Internet addresses or not
    """
    # legacy IP only
    DEFAULT = 0 # implemented with bind9
    # Next-Generation Internet
    SCION = 1 # CoreDNS nameserver + sdns resolver installation
    # only configuration is generated,
    #  and user must provide binaries via DevService herself
    SCION_DEV = 2

    def getHelper(self) -> DNSStackHelperBase:

        if self == DNSStack.SCION:
            return DNSStackHelper()
        else:
            return DNSStackHelperBase()

class DNS_Setup(Option):
    """
    @brief user choice whether the naming system in the emulation
    shall support Next-Gen Internet addresses or not
    Can have different value per AS i.e. both versions can coexist in the same scenario.
    """
    value_type = DNSStack
    @classmethod
    def default(cls):
        return DNSStack.DEFAULT

def _getRRforNode(domain_name: str, addr: str, node: Node=None) -> ResourceRecord:
    """
        return the right resource record for this node
    """
    if node != None:
        if 'scion_address' in  node.getLabel():
            return TXT_RR(name=domain_name, text=f'scion={node.getLabel()['scion_address']}')
        else:
            return A_RR(name=domain_name, address=addr)
    else:
        if ',' in addr: # then it must be a SCION address ISD-ASN,[host-addr]
            return TXT_RR(name=domain_name, text=addr)
        else:
            return A_RR(name=domain_name, address=addr)

def _getNsAddrRecord( node: Node, ns_number: int, zonename: str, addr: str) -> ResourceRecord:
        fqdn = f'ns{str(ns_number)}.{zonename}'
        #return A_RR(name=fqdn, address=addr)
        return _getRRforNode(fqdn, addr, node)

def _getSoaRR(zonename: str) -> ResourceRecord:
    return SOA_RR(zonename='@',
                  mname=f'ns1.{zonename}',
                  rname=f'admin.{zonename}',
                  refresh=900,
                  retry=900,
                  expire=1800,
                  minimum=60 )