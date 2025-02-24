# theese would be circular imports
#from seedemu.core import Node, Router, Network
#from seedemu.core.enums import NodeRole, NetworkType

# alternatives:  InteriorBridgeway, InsideOutConnector, InsideOutGateway
# OutboundAccessProvider, EgressProvider, ExternalReachabilityProvider, External/UplinkProvider
#   ExitPointProvider, LocalNetworkGateway, SimulationExitProvider, OutboundConnectivityProvider
class ExternalConnectivityProvider():
    """!
    @brief this class provides connectivity for emulated nodes 
    from within an emulated network to the external 'real' Internet
    via the hosts network.
    It is the exact opposite of what the RemoteAccessProvider does.

    It achieves this, by making the host's default gateway router into a RealWorldRouter.

    """
    # configureSimulationExit()
    def configureExternalLink(self, emulator: Emulator, netObject: Network, brNode: Node, brNet: Network): # this is probably not the right signature anymore !!
        """
        @param netObject a local network, whose nodes shall have 'external connectivity' through their default gateway
        @param brNode reference to a service node that is not part of the emulation. # does this still apply
            The configureExternalLink method will join the brNet/netObject networks.
            Do not join them manually on the brNode.
        @param brNet reference to a network that is not part of the emulation. (service net)
        This network will have access NAT to the real internet. 
        """
        from seedemu.core import Node, Router, Network
        from seedemu.core.enums import NodeRole, NetworkType
        self._log('setting up ExternalReachability for {} in AS{}...'.format(netObject.getName(), brNode.getAsn()))

        assert netObject.getType() == NetworkType.Local
        assert brNode.getRole() in [NodeRole.Router, NodeRole.BorderRouter], 'only routers may have external reachability'
        brNode.addSoftware('bridge-utils')
        brNode.appendStartCommand('ip route add default via {} dev {}'.format(brNet.getPrefix()[1], brNet.getName()))

        brNode.joinNetwork(brNet.getName())
        brNode.joinNetwork(netObject.getName()) # is it an error to join the same net twice  ?!
    
    def getName(self) -> str:
        return 'IPRoute' # or IPtablesExitProvider sth.