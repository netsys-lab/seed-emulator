from seedemu.core import Emulator, Layer, Node
from seedemu.core.enums import NetworkType
from typing import List
from collections import defaultdict

class EtcHosts(Layer):
    """!
    @brief The EtcHosts layer.

    This layer setups host names for all nodes.
    """

    def __init__(self, only_hosts: bool = True):
        """!
        @brief EtcHosts Layer constructor
        @param only_hosts whether or not to create entries
               for all nodes inluding routers etc. or just hosts
        """
        self._only_hosts = only_hosts
        super().__init__()
        self.addDependency('Base', False, False)

    def getName(self) -> str:
        return "EtcHosts"

    def __getAllIpAddress(self, node: Node) -> list:
        """!
        @brief Get the IP address of the local interface for this node.
        """
        addresses = []
        for iface in node.getInterfaces():
            address = iface.getAddress()
            if iface.getNet().getType() == NetworkType.Bridge:
                pass
            if iface.getNet().getType() == NetworkType.InternetExchange:
                pass
            else:
                addresses.append(address)

        return addresses

    def _getSupportedNodeTypes(self) -> List[str]:
        if self._only_hosts:
            return ['hnode']
        else:
            return ['hnode', 'snode', 'rnode', 'rs']

    def render(self, emulator: Emulator):
        scion_hosts_file_content = []
        hosts_file_content = [] # {address domain.name} mappings
        nodes = [] # targets for /etc/hosts file installation
        scion_nodes = [] # targets for /etc/scion/hosts file installation

        inter_as_nodes = defaultdict(list)

        reg = emulator.getRegistry()
        for ((scope, type, name), node) in reg.getAll().items():
            if type in self._getSupportedNodeTypes():
                addresses = self.__getAllIpAddress(node)
                if 'scion_address' in node.getLabel():
                    scion_addr = node.getLabel()['scion_address']
                    ia_str = scion_addr.split(',')[0]
                    scion_nodes.append(node)
                    for addr in addresses:
                        scion_hosts_file_content.append(f"{ia_str},{addr} {' '.join(node.getHostNames())}")
                        inter_as_nodes[scope].append(f"{addr} {' '.join(node.getHostNames())}")
                else:

                    for address in addresses:
                        hosts_file_content.append(f"{address} {' '.join(node.getHostNames())}")
                        inter_as_nodes[scope].append(f"{address} {' '.join(node.getHostNames())}")
                    nodes.append(node)

        # '10.150.0.71' -> (10,150,0,71)
        sorted_hosts_file_content = sorted(hosts_file_content, key=lambda x: tuple(map(int, x.split()[0].split('.'))))
        sorted_scion_hosts_file_content = sorted(scion_hosts_file_content,
                                                  key=lambda x: tuple(( int( str(x.split(',')[0]).split('-')[0]), # ISD
                                                                      int(x.split()[0].split(',')[0].split('-')[1]), # ASN
                                                                      *map(int, x.split()[0].split(',')[1].split('.')))))

        for node in nodes:
            node.setFile("/tmp/etc-hosts", '\n'.join(sorted_hosts_file_content))
            node.insertStartCommand(0, "cat /tmp/etc-hosts >> /etc/hosts")

        for node in scion_nodes:
            node.setFile("/tmp/etc-scion-hosts", '\n'.join(sorted_scion_hosts_file_content))

            sorted_intra_as_nodes = sorted(inter_as_nodes[node.getRegistryInfo()[0]],#[node.getAsn()],
                                           key=lambda x: tuple(map(int, x.split()[0].split('.'))))
            node.setFile("/tmp/etc-hosts", '\n'.join(sorted_intra_as_nodes))

            node.insertStartCommand(0, "cat /tmp/etc-hosts >> /etc/hosts")

            node.insertStartCommand(0, "cat /tmp/etc-scion-hosts >> /etc/scion/hosts")