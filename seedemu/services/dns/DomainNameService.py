from __future__ import annotations
from seedemu.core import Node, Printable, Emulator, Service, Server, BaseOption
from seedemu.core.enums import NetworkType
from typing import List, Dict, Tuple, Set
from re import sub
import inspect
import requests
from seedemu.core import CAServerBase
from .DNSCommon import ( ResourceRecord, _getRRforNode, _getNsAddrRecord, _getSoaRR,
                         NS_RR, DNSStack, A_RR, TXT_RR, rrname2Type, DNSStackHelperBase,
                         DNSAuth)


DomainNameServiceFileTemplates: Dict[str, str] = {}
ROOT_ZONE_URL = 'https://www.internic.net/domain/root.zone'

DomainNameServiceFileTemplates['named_options'] = '''\
options {
	directory "/var/cache/bind";
	recursion no;
	dnssec-validation no;
    empty-zones-enable no;
	allow-query { any; };
    allow-update { any; };
};
'''


DomainNameServiceFileTemplates['bind9_tls_block'] = '''\
tls local-tls-{zone} {{
 	key-file "{key_path}";
 	cert-file "{cert_path}";
}};
'''

# DoH endpoint description
DomainNameServiceFileTemplates['bind9_http'] = '''\
http local-http-server {
 	# multiple paths can be specified
 	endpoints { "/dns-query";  };
};
'''

# CoreDNS 'server-block'
DomainNameServiceFileTemplates['coredns_config'] = '''\
{schema}://{zone}:{port} {{
tls {tls_cert} {tls_key}
{file}
debug
log
errors
}}
'''

DomainNameServiceFileTemplates['coredns_file'] = '''\
file {zonefile} {zone}
'''

DomainNameServiceFileTemplates['coredns_rhine'] = '''\
rhine {signed_zonefile} {zone} {{
    scion on
}}

sign {zonefile} {zone} {{
    rcert file {rcertfile}
    key file {sign_key_base_path}
    directory {out_dir}
}}
'''



class Zone(Printable):
    """!
    @brief Domain name zone.
    """
    __zonename: str
    __subzones: Dict[str, Zone]
    __records: List[ResourceRecord]
    __gules: List[ResourceRecord]
    # TODO: maybe make it a Dict[str, List[str]], so a name can point to multiple vnodes?
    __pending_records: Dict[str, str]

    def __init__(self, name: str):
        """!
        @brief Zone constructor.

        @param name full zonename.
        """
        self.__zonename = name
        self.__subzones = {}
        self.__records = [
            '$TTL 300',
            '$ORIGIN {}'.format(name if name != '' else '.')
        ]
        self.__gules = []
        self.__pending_records = {}

    def getName(self) -> str:
        """!
        @brief Get zonename.

        @returns zonename.
        """
        return self.__zonename

    def getSubZone(self, name: str) -> Zone:
        """!
        @brief Get a subzone, if not exists, a new one will be created.

        @param name partial zonename. For example, if current zone is "com.", to
        get "example.com.", use getSubZone("example")

        @returns zone.
        @throws AssertionError if invalid zonename.
        """
        assert '.' not in name, 'invalid subzone name "{}"'.format(name)
        if name in self.__subzones: return self.__subzones[name]
        self.__subzones[name] = Zone('{}.{}'.format(name, self.__zonename if self.__zonename != '.' else ''))
        return self.__subzones[name]

    def getSubZones(self) -> Dict[str, Zone]:
        """!
        @brief Get all subzones.

        @return subzones dict.
        """
        return self.__subzones

    def addRecord(self, record: ResourceRecord) -> Zone:
        """!
        @brief Add a new record to zone.

        @todo NS?

        @returns self, for chaining API calls.
        """
        self.__records.append(record)

        return self

    def deleteRecord(self, record: ResourceRecord) -> Zone:
        """!
        @brief Delete the record from zone.

        @todo NS?

        @returns self, for chaining API calls.
        """
        self.__records.remove(record)

        return self

    def addGuleRecord(self, fqdn: str, addr: str, node: Node = None) -> Zone:
        """!
        @brief Add a new gule record.

        Use this method to register a name server in the parent zone.

        @param fqdn full domain name of the name server.
        @param addr IP address of the name server.

        @returns self, for chaining API calls.
        """
        if fqdn[-1] != '.': fqdn += '.'
        zonename = self.__zonename if self.__zonename != '' else '.'
        self.__gules.append(_getRRforNode(fqdn, addr, node))
        self.__gules.append( NS_RR(zonename=zonename, nsname=fqdn) )

        return self

    def resolveTo(self, name: str, node: Node) -> Zone:
        """!
        @brief Add a new A record, pointing to the given node.

        @param name name.
        @param node node.

        @throws AssertionError if node does not have valid interfaces.

        @returns self, for chaining API calls.
        """

        address: str = None
        ifaces = node.getInterfaces()
        assert len(ifaces) > 0, 'Node has no interfaces.'
        for iface in ifaces:
            net = iface.getNet()
            if net.getType() == NetworkType.Host or net.getType() == NetworkType.Local:
                address = iface.getAddress()
                break

        assert address != None, 'Node has no valid interfaces.'
        self.__records.append(_getRRforNode(name, address, node))

        return self

    def resolveToVnode(self, name: str, vnode: str) -> Zone:
        """!
        @brief Add a new resource record (A or TXT record),
                pointing to the given virtual node name.

        @param name name.
        @param vnode  virtual node name.

        @returns self, for chaining API calls.
        """
        self.__pending_records[name] = vnode

        return self

    def resolvePendingRecords(self, emulator: Emulator):
        """!
        @brief resolve pending records in this zone.

        @param emulator emulator object.
        """
        for (domain_name, vnode_name) in self.__pending_records.items():
            pnode = emulator.resolvVnode(vnode_name)

            ifaces = pnode.getInterfaces()
            assert len(ifaces) > 0, 'resolvePendingRecords(): node as{}/{} has no interfaces'.format(pnode.getAsn(), pnode.getName())
            addr = ifaces[0].getAddress()

            self.addRecord(_getRRforNode(domain_name, addr, pnode))

    def getPendingRecords(self) -> Dict[str, str]:
        """!
        @brief Get pending records.

        @returns dict, where key is domain name, and value is vnode name.
        """
        return self.__pending_records

    def getRecords(self) -> List[str]:
        return [ str(r) for r in self.getRRecords()]

    def getRRecords(self) -> List[ResourceRecord]:
        """!
        @brief Get all records.

        @return list of records.
        """
        return self.__records

    def getGuleRRecords(self) -> List[ResourceRecord]:
        return self.__gules

    def getGuleRecords(self) -> List[str]:
        """!
        @brief Get all gule records.

        @return list of records.
        """
        return [str(r) for r in self.__gules]

    def findRecords(self, keys: Dict[str,str]) -> List[ResourceRecord]:

        assert 'type' in keys, 'search key requires RR type! i.e. A, NS, SOA, TXT etc. '

        def cmp_search_key(rr: ResourceRecord, keys: Dict[str, str]) -> bool:
            result = True # by default only the RR type is matched against
                          # (all RRs of this type are returned)
            match rr:
                case A_RR(address, name):
                    if rrname2Type(keys['type']) == A_RR:
                        if 'address' in keys:
                            if keys['address'] != address:
                                return False
                        if 'name' in keys:
                            if keys['name'] != name:
                                return False
                        return result

                    else:
                        return False





        return list(filter(lambda x: cmp_search_key(x,keys) , self.__records))

    def findRecordsKey(self, keyword: str) -> List[ResourceRecord]:
        """!
        @brief Find a record.

        @param keyword keyword.

        @return list of records.
        """
        return [ r for r in self.__records if keyword in str(r) ]

    def print(self, indent: int) -> str:
        out = ' ' * indent
        zonename = self.__zonename if self.__zonename != '' else '(root zone)'
        out += 'Zone "{}":\n'.format(zonename)

        indent += 4
        out += ' ' * indent
        out += 'Zonefile:\n'

        indent += 4
        for record in self.__records:
            out += ' ' * indent
            out += '{}\n'.format(record)

        indent -= 4
        out += ' ' * indent
        out += 'Subzones:\n'

        indent += 4
        for subzone in self.__subzones.values():
            out += subzone.print(indent)

        return out

class DomainNameServer(Server):
    """!
    @brief The domain name server.
    """

    __zones: Set[Tuple[str, bool]]
    __node: Node # only known after configure()
    __ns_server_name: Dict[str,str] # only known after configure()
    __is_master: bool
    __is_real_root: bool

    def __init__(self, do_enc: bool, dns_auth: DNSAuth):
        """!
        @brief DomainNameServer constructor.
        """
        super().__init__()

        self.__zones = set()
        self.__is_master = False
        self.__is_real_root = False
        self.__ns_server_name = {}
        self.__enable_https_func = None
        self.__do_enc = do_enc
        self.__dns_auth = dns_auth

    def _getCryptoPathsForZone(self, zone: str, ns_name: str = None) ->Tuple[str,str]:
        """
        returns (cert_path, key_path) tuple for the given zone
        @param zone zonename of the zone, for which the certificate is issued
        @param ns_name  domain name of the nameserver holding the certificate (usually sth. like 'ns1.zonename.' )
                        #FIXME Actually unnecessary because all nameservers of the same zone have the same certificate right ?!
        """
        assert zone != '', 'invalid input'
        crypto_path = '/etc/coredns/ca'
        cert_path = f'{crypto_path}/{zone}-cert.pem'
        key_path = f'{crypto_path}/{zone}-key.pem'
        return (cert_path, key_path)


    def setCAServer(self, ca: CAServerBase):
        """
        DNS over Encrypted Transport requires the nameservers to have TLS certs
        just like webservers
        """
        # once we are configure()'d  and know our 'node' and server-name
        # we can invoke this callback and pass our node and svc-name as arguments
        self.__enable_https_func = ca.enableHTTPSFunc

        return self


    def addZone(self, zonename: str, createNsAndSoa: bool = True) -> DomainNameServer:
        """!
        @brief Add a zone to this node.

        @param zonename name of zone to host.
        @param createNsAndSoa add NS and SOA (if doesn't already exist) to zone.

        You should use DomainNameService.hostZoneOn to host zone on node if you
        want the automated NS record to work.

        @returns self, for chaining API calls.
        """
        self.__zones.add((zonename, createNsAndSoa))

        return self

    def setMaster(self) -> DomainNameServer:
        """!
        @brief set the name server to be master name server.

        @returns self, for chaining API calls.
        """
        self.__is_master = True

        return self

    def setRealRootNS(self) -> DomainNameServer:
        """!
        @brief set the name server to be a real root name server.

        @returns self, for chaining API calls.
        """
        self.__is_real_root = True

        return self

    def getNode(self) -> Node:
        """!
        @brief get node associated with the server. Note that this only works
        after the services is configured.
        """
        return self.__node

    def getZones(self) -> List[str]:
        """!
        @brief Get list of zones hosted on the node.

        @returns list of zones.
        """
        zones = []
        for (z, _) in self.__zones: zones.append(z)
        return zones

    def print(self, indent: int) -> str:
        out = ' ' * indent
        (scope, _, name) = self.__node.getRegistryInfo()
        out += 'Zones on as{}/{}:\n'.format(scope, name)
        indent += 4
        for (zone, _) in self.__zones:
            out += ' ' * indent
            if zone == '' or zone[-1] != '.': zone += '.'
            out += '{}\n'.format(zone)

        return out


    def __getRealRootRecords(self):
        """!
        @brief Helper tool, get real-world root zone records list by
        RIPE RIS.

        @throw AssertionError if API failed.
        """
        rules = []
        rslt = requests.get(ROOT_ZONE_URL)

        assert rslt.status_code == 200, 'RIPEstat API returned non-200'

        rules_byte = rslt.iter_lines()

        for rule_byte in rules_byte:
            line_str:str = rule_byte.decode('utf-8')
            if not line_str.startswith('.'):
                rules.append(line_str)

        return rules

    def getHostAddr(self, node: Node) -> str:
        ifaces = node.getInterfaces()
        assert len(ifaces) > 0, 'node has no interfaces'
        assert len(ifaces) == 1, 'node is not a host'
        addr = ifaces[0].getAddress()
        return addr

    def getServerName(self, zone: str) -> str:
        """
        returns the domain name of this nameserver in the given zone
        """
        return self.__ns_server_name[zone]

    def configure(self, node: Node, dns: DomainNameService):
        """!
        @brief configure the node.
        """
        self.__node = node

        for (_zonename, auto_ns_soa) in self.__zones:
            zone = dns.getZone(_zonename)
            zonename = zone.getName()

            if auto_ns_soa:
                addr = self.getHostAddr(node)

                if self.__is_master:
                    dns.addMasterIp(zonename, str(addr))

                if zonename[-1] != '.': zonename += '.'
                # handle special '.' rootnameserver case
                if zonename == '.': zonename = ''
                _zone = zonename if zonename!='' else '.'

                # (auto) generate a SOA record, if the zone doesn't already has one
                if len(zone.findRecordsKey('SOA')) == 0:
                    zone.addRecord(_getSoaRR(zonename))


                #If there are multiple zone servers, increase the NS number for ns name.
                ns_number = 1
                while (True):

                    if ( (len(zone.findRecords( keys= { 'name': f'ns{ns_number}.{zonename}',
                                                      'type': 'A'  } )) > 0)
                        or len(zone.findRecords( keys= { 'name': f'ns{ns_number}.{zonename}',
                                                      'type': 'TXT'  } )) > 0):
                        ns_number +=1
                    else:
                        break

                ns_name=f'ns{str(ns_number)}.{zonename}'
                self.__ns_server_name[_zone] = ns_name
                if self.__do_enc:
                    assert self.__enable_https_func, 'CAServer required for DoE'
                    cert_names = [self.getServerName(_zone), _zone] # the SNI's for which the certificate is needed

                    cert_path, key_path = self._getCryptoPathsForZone(_zone, ns_name)
                    # request a certificate for '$server_name' from the CA
                    self.__enable_https_func(node = node,
                                             context = 'dns',
                                             server_names = cert_names,
                                             dst_cert_path = cert_path,
                                             dst_key_path = key_path)
                zone.addGuleRecord(ns_name, str(addr), node)
                zone.addRecord(_getNsAddrRecord(node, ns_number, zonename, str(addr) ))
                zone.addRecord( NS_RR(zonename='@', nsname=ns_name) )

                # TODO if parent zone doesn't have a DS record yet add one (if self.dns_auth != DNSAuth.NONE)

            if zone.getName() == "." and self.__is_real_root:
                for record in self.__getRealRootRecords():
                    zone.addRecord(record)

        self._installRHINEcert(node)

    def _installRHINEcert(self, node: Node):
        """ generate RHINE cert
        """
        # for simplicity we could just re-use the TLS certificates..

        h = self.__dns_auth.getServerHelper()
        rcert_path, rkey_path = h.getRhinePaths()
        rcert_names = h.getRhineCertName()
        # Rcert should be valid for all of the servers zones
        dnames = [ z for z,_ in self.__zones] + [ self.getServerName(z) for z,_ in self.__zones ]

        # TODO use /usr/local/share/ca-certificates/SEEDEMU_Internal_Root_CA.crt"
        # MiniCA root cert on the client side to verify the server's RHINE cert

        self.__enable_https_func(node = node,
                                 context = 'rhine',
                                 #server_names = [rcert_names],
                                 server_names = dnames,
                                 dst_cert_path = rcert_path,
                                 dst_key_path = rkey_path)

    def install(self, node: Node, dns: DomainNameService):
        """!
        @brief Handle the installation.
        """
        assert node == self.__node, 'configured node differs from install node.\
                                     Please check if there are conflict bindings'

        node.appendClassName(dns.getName())
        opt = node.getOption('dns_setup')
        if opt == None:
            for o in dns.getAvailableOptions():
                node.setOption(o)
        if (val:=node.getOption('dns_setup').value) == DNSStack.DEFAULT:
            if self.__do_enc:
                #'bind9 is only capable of DNS-over-HTTPS (DoH) and DNS-over-TLS (DoT) not DNS-over-QUIC (DoQ) yet'
                raise NotImplementedError
            if self.__dns_auth != DNSAuth.NONE:
                raise NotImplementedError

            self._do_install_bind9(node, dns)
        elif val in [DNSStack.SCION, DNSStack.SCION_DEV]:
            assert self.__do_enc, 'No support for unencrypted DNS in the Future Next Generation Internet anymore !'
            # TODO: maybe mandate "RHINE" here .. ?!
            assert self.__dns_auth in [DNSAuth.NONE, DNSAuth.RHINE], 'legacy DNSSEC not supported in the NextGen Internet!'
            self._do_install_coredns(node, dns, val.getHelper())

    def _do_generate_zone_signing_keys(self, node: Node, dns: DomainNameService, zone_signing_keys_path: str):
        """ generate a zone signing key pair for each of the zones 
        
        """

        for (_zonename, auto_ns_soa) in self.__zones:
            zone = dns.getZone(_zonename)
            zonename = filename = zone.getName()
            if zonename == '' or zonename == '.':
                filename = 'root'
                zonename = '.'
            node.appendStartCommand(f'mkdir -p {zone_signing_keys_path}')
            keypath = f'{zone_signing_keys_path}'# /{filename}'
            node.addSoftware('rename')
            node.addSoftware('bind9utils')
            zn = zone.getName()
            # ns.example.com. -> ns\.example\.com\.
            zn2 = '\.'.join( zone.getName().split('.')).rstrip('\.') if zn!='.' else ''
            zn3 = zn2 if zn != '.' else 'root'
            
            # signing key type must match the one of RHINE cert !!
            node.appendStartCommand(f"cd {keypath} && dnssec-keygen -a ED25519 -f KSK -n ZONE {zn} && ls | xargs -d '\\n' -n 1 rename 's/K{zn2}\.\+[0-9]+\+[0-9]+\./K{zn3}\./'") # rename signing key files to 'K{zonefilename}'

    def _do_generate_zonefiles(self, node: Node, dns: DomainNameService, zones_path: str):
        """ generate a zonefile for each of the zones under /etc/coredns/zones
        TODO zonefiles are just a RR-dump and thus the impl could be shared between bind9 and coredns
        """

        for (_zonename, auto_ns_soa) in self.__zones:
            zone = dns.getZone(_zonename)
            zonename = filename = zone.getName()
            if zonename == '' or zonename == '.':
                filename = 'root'
                zonename = '.'
            zonepath = f'{zones_path}/{filename.rstrip('.')}.db'
            node.setFile(zonepath, '\n'.join(zone.getRecords()))

    def _do_generate_corefile(self, node: Node, dns: DomainNameService,
                               corefile_path: str,
                               zones_path: str,
                               signed_zones: str,
                               zone_signing_keys_path: str):
        """ add a server-block to Corefile for each zone
        """

        node.setFile(corefile_path, '')
        for (_zonename, auto_ns_soa) in self.__zones:
            zone = dns.getZone(_zonename)
            zonename = filename = zone.getName()
            if zonename == '' or zonename == '.':
                filename = 'root'
                zonename = '.'

            #  TLS certificate and private key for zone are generated by _enableHttpsFunc
            cert_path, key_path = self._getCryptoPathsForZone(zonename, self.getServerName(zonename) )
            
            zonefile_path = f'{zones_path}/{filename.rstrip('.')}.db'
            node.appendStartCommand(f'mkdir -p {signed_zones}')
            signed_zonefile_path = f'{signed_zones}/db{ '.root' if zonename=='.' else f'.{zonename.rstrip('.')}' }.signed'
            h = self.__dns_auth.getServerHelper()
            rhinecertpath, _ = h.getRhinePaths()

            _file = ( DomainNameServiceFileTemplates['coredns_file'].format(zonefile=zonefile_path, zone=zonename) 
                      if self.__dns_auth == DNSAuth.NONE else 
                       DomainNameServiceFileTemplates['coredns_rhine'].format(signed_zonefile=signed_zonefile_path,
                                                                              zonefile=zonefile_path,
                                                                              zone=zonename,
                                                                              rcertfile=rhinecertpath,
                                                                              sign_key_base_path=f'{zone_signing_keys_path}/K{filename.rstrip('.')}', # or use filename here ?
                                                                              out_dir=signed_zones ) )
            
            server_block = DomainNameServiceFileTemplates['coredns_config'].format(
                schema='squic', # SCION QUIC or change to DoQ sth. 
                file=_file,
                zone= zonename,
                port=853,# standard DoQ port,
                tls_cert=cert_path,
                tls_key=key_path
            )
            node.appendFile(corefile_path, server_block)

    def _do_install_coredns(self, node: Node, dns: DomainNameService, helper: DNSStackHelperBase):
        """!@ installs and configures coredns server on the given node
        @note see https://coredns.io/manual/configuration/
        """

        # install coredns binaries onto node
        helper.install(node, 'coredns')

        corefile_path = f'/etc/coredns/Corefile'
        zones_path = '/etc/coredns/zones' # 'raw' zonesfiles without 'DNSKEY, RRSIG etc.'
        signed_zones_path = '/etc/coredns/signed_zones' # zonefiles with additional RRSIG entries
        zone_signing_keys_path = '/etc/coredns/keys'
        self._do_generate_zonefiles(node, dns, zones_path)
        if self.__dns_auth != DNSAuth.NONE:
            self._do_generate_zone_signing_keys(node, dns, zone_signing_keys_path)
        # TODO move corefile generation to after-configure() when server-name is known
        self._do_generate_corefile(node, dns, corefile_path,
                                   zones_path,
                                   signed_zones=signed_zones_path,
                                   zone_signing_keys_path=zone_signing_keys_path)
        node.addSoftware('apache2-utils') # for rotatelogs
        node.appendStartCommand(f'coredns -conf {corefile_path} 2>&1 | rotatelogs -n 2 /var/log/coredns.log 1M', fork=True)

    def _do_install_bind9(self, node: Node, dns: DomainNameService):
            """!@brief installs the default bind9 DNS stack onto the given node
                @details the node will run 'named' service
            """
            #TODO i bet bind9 is capable of DoE as well... go and implement it

            '''
            # sets the contents of the following config files:
              - /etc/bind/named.conf.local    --includes-->   /etc/bind/named.conf.zones
              - /etc/bind/named.conf.zones    contains pointers to  zonefiles from /etc/bind/zones/*
              - /etc/bind/zones/*             directory with actual zone files
              - /etc/bind/named.conf.options   general options for 'named'
            '''

            node.addSoftware('bind9')
            node.appendStartCommand('echo "include \\"/etc/bind/named.conf.zones\\";" >> /etc/bind/named.conf.local')
            node.setFile('/etc/bind/named.conf.options',
                          DomainNameServiceFileTemplates['named_options'])

            '''
            #TODO implement encrypted DNS for bind9
            Add the following to options{} block:

                'https-port 443;'

                'listen-on port 443 tls local-tls http local-http-server {any;};'
            And:

                DomainNameServiceFiletemplates['bind9_http']

                outside the options{} block in the .conf.options file

            ...to enable DoH with bind
            '''

            node.setFile('/etc/bind/named.conf.zones', '')

            for (_zonename, auto_ns_soa) in self.__zones:
                zone = dns.getZone(_zonename)
                zonename = filename = zone.getName()

                if zonename == '' or zonename == '.':
                    filename = 'root'
                    zonename = '.'
                zonepath = '/etc/bind/zones/{}'.format(filename)
                node.setFile(zonepath, '\n'.join(zone.getRecords()))

                if self.__is_master:
                    node.appendFile('/etc/bind/named.conf.zones',
                            'zone "{}" {{ type master; notify yes; allow-transfer {{ any; }}; file "{}"; allow-update {{ any; }}; }};\n'.format(zonename, zonepath)
                        )
                elif zone.getName() in dns.getMasterIp().keys(): # Check if there are some master servers
                    master_ips = ';'.join(dns.getMasterIp()[zone.getName()])
                    node.appendFile('/etc/bind/named.conf.zones',
                        'zone "{}" {{ type slave; masters {{ {}; }}; file "{}"; }};\n'.format(zonename, master_ips, zonepath)
                    )
                else:
                    node.appendFile('/etc/bind/named.conf.zones',
                        'zone "{}" {{ type master; file "{}"; allow-update {{ any; }}; }};\n'.format(zonename, zonepath)
                    )

            node.appendStartCommand('chown -R bind:bind /etc/bind/zones')
            node.appendStartCommand('service named start')

class DomainNameService(Service):
    """!
    @brief The domain name service.
    """

    __rootZone: Zone
    __autoNs: bool
    __masters: Dict [str, List[str]]

    @classmethod
    def getAvailableOptions(self):
        from seedemu.core import OptionRegistry
        return [OptionRegistry().dns_setup()]

    def __init__(self, autoNameServer: bool = True, dns_setup: BaseOption = None,
                 do_enc: bool = True, dns_auth: DNSAuth = DNSAuth.NONE):
        """!
        @brief DomainNameService constructor.
        @param do_enc enable DNS over Encrypted Transport.
                (requires DNS nameservers to have TLS certs, and clients to posess the root cert to verify them)
        @param autoNameServer add gule records to parents automatically.
        @param dns_auth enable authentication of DNS RR's i.e. via DNSSEC
        """
        from seedemu.core.OptionRegistry import OptionRegistry
        super().__init__()
        self.__dsn_auth = dns_auth
        self.__autoNs = autoNameServer
        self.__rootZone = Zone('.')
        self.__masters = {}
        self.__do_enc = do_enc
        self.addDependency('Base', False, False)

        args = inspect.signature(DomainNameService.__init__).parameters.keys()
        vals = locals()
        option_names = [name for name in args
                        if (vals[name] is not None) and
                        name not in ['self', 'autoNameServer', 'do_enc', 'dns_auth'] ]
        assert not any([ vals[name].name != name and
                        not vals[name].name.endswith(name) for name in option_names]), 'option-parameter mismatch!'


        # let user override the global default options

        for n in option_names:
        # Replace the 'defaults' class methods dynamically
            v = vals[n]
            opt_cls = type(v)
            # Capture 'new_value' as default argument (forces a snapshot of the current value)
            opt_cls.default = classmethod(lambda cls, new_value=v.value: new_value)
            opt_cls.defaultMode = classmethod(lambda cls, newmode=v.mode: newmode)
            prefix = getattr(opt_cls, '__prefix') if hasattr(opt_cls, '__prefix') else None
            OptionRegistry().register(opt_cls, prefix)

    def __autoNameServer(self, zone: Zone, lvl: int =0):
        """!
        @brief Try to automatically add NS & DS records of children to parent zones.
        @param lvl the current level in the qname starting from the right. (0 is '.' root, 1 is 'com.' etc.)
        @param zone root zone reference.
        """
        if (len(zone.getSubZones().values()) == 0): return
        self._log('Collecting subzones NSes of "{}"...'.format(zone.getName()))
        for subzone in zone.getSubZones().values():
            for gule in subzone.getGuleRecords(): 
                zone.addRecord(gule)
            # add zone delegation records for DNSSEC/RHINE
            if self.__dsn_auth == DNSAuth.DNSSEC:
                # TODO add DS RR
                raise NotImplementedError
            if self.__dsn_auth == DNSAuth.RHINE:
                # _dsp.	    604800	IN	TXT	"com"     # in '.' zone
                # _dsp.com.	604800	IN	TXT	"example" # in 'com.' zone
                nexttokens = subzone.getName().rstrip('.').split('.')
                token = zone.getName().rstrip('.').split('.')
                # assert len(nexttokens) == len(token)+1, 'logic error - subzone must have Lvl of parent zone plus ones'
                nextlvlname = nexttokens[len(nexttokens)-1-lvl]
                
                lvlname = token[len(token)-1] if lvl!=0 else ''
                zone.addRecord(TXT_RR(name=f'_dsp.{lvlname}', text=f"{nextlvlname}"))
                
            self.__autoNameServer(subzone, lvl+1)

    def __resolvePendingRecords(self, emulator: Emulator, zone: Zone):
        zone.resolvePendingRecords(emulator)
        self._log('resloving pending records for zone "{}"...'.format(zone.getName()))
        for subzone in zone.getSubZones().values():
            self.__resolvePendingRecords(emulator, subzone)

    def _createServer(self) -> Server:
        return DomainNameServer(self.__do_enc, self.__dsn_auth)

    def _doConfigure(self, node: Node, server: DomainNameServer):
        server.configure(node, self)

    def configure(self, emulator: Emulator):

        self.__resolvePendingRecords(emulator, self.__rootZone)
        return super().configure(emulator)

    def _doInstall(self, node: Node, server: DomainNameServer):
        server.install(node, self)

    def getName(self):
        return 'DomainNameService'

    def getConflicts(self) -> List[str]:
        return ['DomainNameCachingService']

    def getZone(self, domain: str) -> Zone:
        """!
        @brief Get a zone, create it if not exist.

        This method only create the zone. Host it with hostZoneOn.

        @param domain zone name.

        @returns zone handler.
        """
        if domain == '.' or domain == '': return self.__rootZone
        path: List[str] = sub(r'\.$', '', domain).split('.')
        path.reverse()
        zoneptr = self.__rootZone
        for z in path:
            zoneptr = zoneptr.getSubZone(z)

        return zoneptr

    def getRootZone(self) -> Zone:
        """!
        @brief Get the root zone.

        @return root zone.
        """
        return self.__rootZone

    def getZoneServerNames(self, domain: str) -> List[str]:
        """!
        @brief Get the names of servers hosting the given zone. This only works
        if the server was installed by using the "installByName" call.

        @param domain domain.

        @returns list of tuple of (node name, asn)
        """
        info = []
        targets = self.getPendingTargets()

        for (vnode, sobj) in targets.items():
            server: DomainNameServer = sobj

            hit = False

            for zone in server.getZones():
                if zone.getName() == domain:
                    info.append(vnode)
                    hit = True
                    break

            if hit: continue

        return info

    def addMasterIp(self, zone: str, addr: str) -> DomainNameService:
        """!
        @brief add master name server IP address.

        @param addr the IP address of master zone server.
        @param zone the zone name, e.g : com.

        @returns self, for chaining API calls.
        """
        if zone in self.__masters.keys():
            self.__masters[zone].append(addr)
        else:
            self.__masters[zone] = [addr]

        return self

    def setAllMasterIp(self, masters: Dict[str: List[str]]):
        """!
        @brief override all master IPs, to be used for merger. Do not use unless
        you know what you are doing.

        @param masters master dict.
        """
        self.__masters = masters

    def getMasterIp(self) -> Dict [str, List[str]]:
        """!
        @brief get all master name server IP address.

        @return list of ip address
        """
        return self.__masters

    def render(self, emulator: Emulator):
        if self.__autoNs:
            self._log('Setting up NS records...')
            self.__autoNameServer(self.__rootZone)

        super().render(emulator)

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'DomainNameService:\n'

        indent += 4
        out += self.__rootZone.print(indent)

        return out

