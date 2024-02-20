from __future__ import annotations
from enum import Enum
from typing import Dict, Tuple

from seedemu.core import (Emulator, Node, Interface, Layer, Network, Registry,
                          Router, ScionAutonomousSystem, ScionRouter,
                          ScopedRegistry, Graphable)
from seedemu.core.ScionAutonomousSystem import IA
from seedemu.layers import ScionBase, ScionIsd # Scion, LinkType

route_tmpl = """route 10.{to}.0.0/24 via 10.{via}.0.71 {{ bgp_large_community.add(LOCAL_COMM); }};"""

bgp_tmpl = """
        protocol static staticroutes {{
            ipv4 {{
                table t_bgp;
            }};
            {routes}
        }}
"""

class ScionSbas(Layer, Graphable):
    """!
    @brief This layer manages SBAS instances.

    TODO: At the moment it would be the simplest to have a single SBAS instance per emulation
    """

    __asn: int

    # List of ASes that are all pops of the single SBAS instance
    __pops: [int]

    # Map of ASes to customers
    # The first key is the AS number of the SBAS pop, the second one is the customer asn
    __customers: Dict[int, Dict[str, int]]

    
    def __init__(self):
        """!
        @brief SCION layer constructor.
        """
        super().__init__()
        self.__pops = []
        self.__customers = {}
        self.__asn = 0

    def getName(self) -> str:
        return "ScionSbas"

    
    def configure(self, emulator: Emulator) -> None:
        reg = emulator.getRegistry()
        base_layer: ScionBase = reg.get('seedemu', 'layer', 'Base')
        assert issubclass(base_layer.__class__, ScionBase)

        # self._configure_links(reg, base_layer)


    def render(self, emulator: Emulator) -> None:
        """!
        @brief 
        """
        reg = emulator.getRegistry()
        base_layer: ScionBase = reg.get('seedemu', 'layer', 'Base')
        assert issubclass(base_layer.__class__, ScionBase)

        print(self.__customers)
        print(self.__pops)
        # What to do:
        # Find CS nodes and router nodes
        # Get all prefixes for all SBAS pops and other customers
        # Only prefixes of customer networks are announced and accessible
        for ((scope, type, name), obj) in reg.getAll().items():
            if type in ['csnode']:
                node: Node = obj
                asn = node.getAsn()
                as_: ScionAutonomousSystem = base_layer.getAutonomousSystem(asn)
                asn = as_.getAsn()

                # node.addSoftware("traceroute")

                # If there is a CS that is not inside of a pop, just ignore it
                if asn not in self.__pops:
                    continue

                # get a list of pops that are not the current one
                other_pops = [pop for pop in self.__pops if pop != asn]

                # create a sig for the current pop
                # TODO: Remove hardcoded addr dependency here
                as_.createSig(f"sig-1", f"10.{asn}.0.0/24", f"10.{asn}.0.71")

                
                print("CSNODE ", asn)
                # customers = {152: {"customer": 153, "ix": 101}}
                for pop in other_pops:
                    customers = []
                    # Create a list of all customers for a given pop and connect them
                    # customers = [c for p, c in self.__customers.items() if p["customer"] == pop]
                    for p, c in self.__customers.items():
                        if p == pop:
                            customers.append(pop)
                            for index, customer in enumerate(c["customers"]):
                                 customers.append(c["customers"][index])
                                 customers.append(c["ixes"][index])
                            
                            # customers.append(pop)
                            #customers.append(c["customer"])
                            #customers.append(c["ix"])

                    as_.connectSig(f"sig-1", [f"10.{c}.0.0/24" for c in customers], f"1-{pop}")
                    
                for pop, c in self.__customers.items():
                    if pop == asn:
                        # Add routes for own customers to be sent through whatever router?!
                        # TODO: Double check what happens if there are multiple customers in the same IX
                        # TODO: Support routers with different IXes
                        for index, customer in enumerate(c["customers"]):
                            node.appendStartCommand(f"ip route add 10.{c['ixes'][index]}.0.0/24 via 10.{asn}.0.253")       
                            node.appendStartCommand(f"ip route add 10.{c['customers'][index]}.0.0/24 via 10.{asn}.0.253")
              
            # pops = [150, 152]
            # customers = {150: 151, 152: 153}

            if type in ['rnode']:
                node: Node = obj
                asn = node.getAsn()
                as_: ScionAutonomousSystem = base_layer.getAutonomousSystem(asn)
                asn = as_.getAsn()

                # node.addSoftware("traceroute")

                # If there is a CS that is not inside of a pop, just ignore it
                if asn not in self.__pops:
                    continue

                print("WOKRING ON ROUTER NODE ", asn)
                customer_routes = []
                for pop, c in self.__customers.items():
                    if pop != asn:
                        for index, customer in enumerate(c["customers"]):
                            customer_routes.append(route_tmpl.format(to=c['customers'][index], via=asn))
                            customer_routes.append(route_tmpl.format(to=pop, via=asn))
                
                tmpl = bgp_tmpl.format(routes="\n".join(customer_routes))
                node.appendStartCommand('echo "{}" >> /etc/bird/bird.conf'.format(tmpl))

        pass

    def setAsn(self, asn: int) -> None:
        """!
        @brief Set the AS number of the SBAS instance.

        @param asn AS number of the SBAS instance
        """
        self.__asn = asn
    
    def addPop(self, asn: int) -> None:
        """!
        @brief Add a pop to the SBAS instance.

        @param asn AS number of the pop
        """
        self.__pops.append(asn)

    def addCustomer(self, pop: int, customer: int, ix: int) -> None:
        """!
        @brief Add a customer to the SBAS instance.

        @param pop AS number of the pop
        @param customer AS number of the customer
        """
        cur_pop = self.__customers.get(pop)
        if cur_pop is None:
            cur_pop = {
                "customers": [],
                "ixes": [],
            }
        
        cur_pop["customers"].append(customer)
        cur_pop["ixes"].append(ix)

        self.__customers[pop] = cur_pop

    def print(self, indent: int = 0) -> str:
        out = ' ' * indent
        out += 'ScionLayer:\n'

        indent += 4
        for (ix, a, b, rel), count in self.__ix_links.items():
            out += ' ' * indent
            out += f'IX{ix}: AS{a} -({rel})-> AS{b}'
            if count > 1:
                out += f' ({count} times)'
            out += '\n'

        for (a, b, rel), count in self.__links.items():
            out += ' ' * indent
            out += f'XC: AS{a} -({rel})-> AS{b}'
            if count > 1:
                out += f' ({count} times)'
            out += '\n'

        return out

    