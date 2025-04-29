from seedemu.core import Node, Option
from enum import Enum
from dataclasses import dataclass
from random import randint

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


class DNSStack(Enum):
    """
    user choice whether the naming system in the emulation
    shall support Next-Gen Internet addresses or not
    """
    # legacy IP only
    DEFAULT = 0 # implemented with bind9
    # Next-Generation Internet
    SCION = 1 # experimental implementation with custom coredns fork

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