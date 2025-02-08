from typing import List, Dict, Tuple
from sys import stderr
from seedemu.layers.Scion import LinkType as ScLinkType

class DataProvider:

    def getAttributes(self, asn: int)->Dict[str,any]:
        """
        @brief returns AS attributes such as MTU
         'type' i.e. ScionAutonomusSystem or ScionMcastAutonomousSystem 
        """
        return {  'latency': 0,
                   'bandwidth':0,
                    'mtu': 1500,
                     'packetDrop': 0 }
    
    def getLinkAttributes(self, asn: int , if_id: int):
        """
        @brief return attributes such as Geo-Location, Bandwidth, LinkType,Latency for staticInfoConfig.json
        that included in PCB static metadata extension
        """
        return {}
    
    """!
    @brief data source for the topology generator.
    """
    def getSCIONCrossConnects(self, from_asn: int) -> Dict[int,List[Tuple[str,ScLinkType,Tuple[int,int]]]]: 
        """
            @brief returns the XC cross connections that this AS has to other ASes
          returns a dict that maps the peer_ASN to a List of Tuples of kind ( address, LinkType, (IFID_a,IFID_b) )
           The peername  required for Node::crossConnect() can be constructed as 'br{}'.format(IFID_b) by the generator

        this is only needed for SCION ASes and hence a default impl is provided
        so that 'normal' BGP ASes need not bother
        """
        return {}

    # maybe just move this to the Attributes map, to not unnecessarily bloat the interface
    def getCertIssuer(self, asn: int ) -> int:
        """
        @brief return the SCION Core AS that issues the certificates for the given non-core AS
        @param ASN of a non-core SCION AS

        this is only needed for SCION ASes and hence a default impl is provided
        so that 'normal' BGP ASes need not bother
        """
        return asn

    # TODO: replace this with a key-value pair in getAttributes()
    def isCore(self, asn: int )-> bool:
        """
        @brief return whether the AS with this ASN is a CORE AS 
        
        this is only needed for SCION ASes and hence a default impl is provided
        so that 'normal' BGP ASes need not bother
        """
        return False
    
    def getASes(self) -> List[int]:
        """
        @brief return a list of all the AutonomousSystems there are
        """
        return NotImplementedError('getASes not implemented')
    
    def getASInterfaces(self, asn: int) ->List[int]:
        """
        @brief each connection to a neighboring AS corresponds to one Interface (IF-)ID
        """
        raise NotImplementedError()

    def getName(self) -> str:
        """!
        @brief Get name of this data provider.

        @returns name of the layer.
        """
        raise NotImplementedError('getName not implemented')

    def getPrefixes(self, asn: int) -> List[str]:
        """!
        @brief Get list of prefixes announced by the given ASN.
        @param asn asn.

        @returns list of prefixes.
        used for AutonomousSystem::createNetwork() by the generator
        and thus may be 'auto'
        """
        raise NotImplementedError('getPrefixes not implemented.')

# The signature of this method just doesn't reflect the realities !!
# Between any two ASes there might be 'transit' and 'peering' links at the same time ?!(doesn't make sense actually).
# should this be asserted here?!

# why not add the Id of the IX where they peer here( because it might be an XC link just as well )
    def getPeers(self, asn: int) -> Dict[int, str]: 
        """!
        @brief Get a dict of peer ASNs of the given ASN.
        @param asn asn.

        @returns dict where key is asn and value is peering relationship.
        the peering relationship is currently used by Ebgp::addPrivatePeering() by the default Generator
        """
        raise NotImplementedError('getPeers not implemented.')

    def getInternetExchanges(self, asn: int) -> List[int]:
        """!
        @brief Get list of internet exchanges joined by the given ASN.
        @param asn asn.

        @returns list of tuples of internet exchange ID. Use
        getInternetExchangeMembers to get other members.
        """
        raise NotImplementedError('getInternetExchanges not implemented.')

    def getInternetExchangeMembers(self, id: int) -> Dict[int, str]:
        """!
        @brief Get internet exchange members for given IX ID.
        @param id internet exchange ID provided by getInternetExchanges.

        @returns dict where key is ASN and value is IP address in the exchange.
        value can also be 'auto' - > it will be used as an argument to Node::joinNetwork()
        Note that if an AS has multiple addresses in the IX, only one should be
        returned.
        """
        raise NotImplementedError('getInternetExchangeMembers not implemented.')

    def getInternetExchangeAttributes(self, id: int) -> Dict[str,any]:
        """@brief return properties such as Latency[ms], Bandwith([bps]), MTU of the peering LAN"""
        return {'latency':0,
                'mtu': 1500,
                'bandwidth': 0,
                'packetDrop': 0}

    def getInternetExchangePrefix(self, id: int) -> str:
        """!
        @brief Get internet exchange peering lan prefix for given IX ID.
        @param id internet exchange ID provided by getInternetExchanges.

        @returns prefix in cidr format.
        used for Base::createInternetExchange() by the default generator  and can be 'auto'
        """
        raise NotImplementedError('getInternetExchangeSubnet not implemented.')

    def _log(self, message: str):
        """!
        @brief Log to stderr.
        """
        print("==== {}DataProvider: {}".format(self.getName(), message), file=stderr)
