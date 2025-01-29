from sys import stderr

from .providers import DataProvider
from . .core import Emulator, AutonomousSystem, InternetExchange, ScionAutonomousSystem, Text
from . .layers import Base, Routing,  Ospf, Scion, ScionBase,ScionRouting, ScionIsd
from seedemu.layers.Scion import LinkType 
from typing import Type, Tuple


info_conf = {}
info_conf['file'] = """{{
{values}
}}"""
info_conf['link_type'] = """
"LinkType": {{
            {linktypes}
}}
"""
info_conf['geo'] = """
    "Geo": {{
           {idgeo}
           }}
"""

class BorderRouterAllocation:
    """
    @brief a strategy object that decides how border routers map to AS interfaces
    """
    def getRouterForIX(self, ix_alias: int) -> Node:
        pass
    def getRouterForXC(self, if_ids, peer_asn: int ) -> Node:
        pass


class SeparateForEachIFAlone(BorderRouterAllocation):

    def __init__(self, _as: AutonomousSystem ):
        self._my_as = _as        

    def getRouterForIX(self, ix_alias : int ):
        br_name = 'router{}'.format(ix_alias)    
        if br_name in self._my_as.getRouters() :
            return self._my_as.getRouter(br_name)
        else:
            brd = self._my_as.createRouter(br_name) 
            # brd.setGeo(Lat=37.7749, Long=-122.4194,Address="San Francisco, CA, USA")
            return brd

    def getRouterForXC(self, ifids, peer_asn: int ):
        # each IFID will get its own dedicated border router
        br_name = 'brd{}'.format(ifids[0])
        peer_br_name = 'brd{}'.format(ifids[1])                    

        if br_name not in self._my_as.getRouters():
            rt = self._my_as.createRouter(br_name )
            #.setGeo(Lat=37.7749, Long=-122.4194,Address="San Francisco, CA, USA")
            return rt,peer_br_name
            
        else:
            return self._my_as.getRouter(br_name), peer_br_name
        


class CommonRouterForAllIF(BorderRouterAllocation):
    def __init__(self, _as: AutonomousSystem):
        self._my_as = _as
        self._my_as.createRouter('brd00')
    def getRouterForIX(self, ix_alias: int ):
        return self._my_as.getRouter('brd00')
    
    def getRouterForXC(self, if_ids, peer_asn: int ):
        return self._my_as.getRouter('brd00'), 'brd00'

class DefaultScionGenerator:
    """!
    @brief Default topology generator implementation.

    The topology generator providers a way to generate emulation scenarios from
    real-world topology.

    WIP.
    TODO: check what happens if a DataProvider has both, XC cross connects and IX exchange points
          this is yet untested
    """

    __provider: DataProvider
    

    def __init__(self, provider: DataProvider , alloc: Type[BorderRouterAllocation] = SeparateForEachIFAlone ):
        """!
        @brief create a new topology generator.

        @param provider data provider.
        """
        self.__provider = provider
        self._alloc_type = alloc
        self.__debug_cnt = 0
        self._link_cache = set()
        self._ixp_to_alias = dict()
        pass

    def __log(self, message: str) -> None:
        """!
        @brief Log to stderr.

        @param message message.
        """
        print('== DefaultGenerator: {}'.format(message), file = stderr)
    
    def _ASNforIXp(self, ix_id: int ) -> int:
        """
        @brief return an ASN for the IXp with id 'ix_id'
        """
        # ASNs of 'real' ASes and those of IXps must not collide , right ?!
        if ix_id in self._ixp_to_alias:
            return self._ixp_to_alias[ix_id]
        else:
            alias = len(self.__provider.getASes()) +3 +ix_id
            self._ixp_to_alias[ix_id]= alias
            return alias


    def __cache_link(self, a: Tuple[int,int], b: Tuple[int,int], rel) -> bool:
        """
        (AS,IF-ID)
        """
        assert len(self._link_cache) == self.__debug_cnt

        key = (frozenset([a,b]),rel)
        # key = ((a,b),rel)
        res =  key in self._link_cache
        self._link_cache.add( key )
        return res

    def __generate(self, asn: int, emulator: Emulator, depth: int):
        """!
        @brief recursively (depth-first) generate topology.

        @param asn Alias ASN to start on.
        @param emulator emulator to commit changes on.
        @param depth levels to traverse.
        """
        if depth <= 0: return

        self.__log('generating AS{}...'.format(asn))

        base: ScionBase = emulator.getLayer('Base')
        scion: Scion = emulator.getLayer('Scion')
        scion_isd: ScionIsd = emulator.getLayer('ScionIsd')
        
        routing: ScionRouting = emulator.getLayer('Routing')

        if asn in base.getAsns():
            self.__log('AS{} already done, skipping...'.format(asn))
            return
        
        self.__log('getting list of IXes joined by AS{}...'.format(asn))
        ixes_joined_by_asn = self.__provider.getInternetExchanges(asn)

        self.__log('getting list of prefixes announced by AS{}...'.format(asn))
        prefixes_of_asn = self.__provider.getPrefixes(asn)

        self.__log('getting list of peers of AS{}...'.format(asn))
        peers = self.__provider.getPeers(asn)

        self.__log('getting list of cross connects of AS{}...'.format(asn))
        cross_connects = self.__provider.getSCIONCrossConnects(asn)
                       
        # construct a new ScionAutonomousSystem
        attr = self.__provider.getAttributes(asn)
        current_as = attr['type']( asn, mhfas=self.__provider.getMHFAs())
        if 'note' in attr:
            current_as.setNote(attr['note'])
        if 'experimental_mcast' in attr:
            current_as.setFeature('experimental_mcast',attr['experimental_mcast'])
        base.setAutonomousSystem(current_as)
        scion_isd.addIsdAs(1, asn, is_core= self.__provider.isCore(asn))
        
        if not self.__provider.isCore(asn):
            issu =  self.__provider.getCertIssuer(asn)
            assert issu != None
            scion_isd.setCertIssuer((1, asn), issuer=issu)

 
        net_count = 0
        nr_prefixes = len(prefixes_of_asn)
        nr_joined_ixes = len(ixes_joined_by_asn)


        self.__log('looking for details of {} IXes joined by AS{}...'.format(len(ixes_joined_by_asn), asn))

        # simplest case
        if nr_prefixes == 1:
            # create one border router for each joined IX and have each join the same net (for the single existing prefix)
            # mot often the prefix will be 'auto' anyway, so we will end up here


            self.__log('creating {} networks for AS{}...'.format(nr_prefixes, asn))
            
            prefix = prefixes_of_asn[0] # there is only one
            netname = 'net{}'.format(net_count)

            self.__log('creating {} with prefix {} for AS{}...'.format(netname, prefix, asn))
            
            net = current_as.createNetwork(netname, prefix)
            if 'mtu' in attr:
                net.setMtu( attr['mtu'] )
            net.setDefaultLinkProperties(latency=attr['latency'],
                                         bandwidth=attr['bandwidth'],
                                         packetDrop=attr['packetDrop'])
            
            cs = current_as.createControlService(f'cs{asn}_0').joinNetwork(netname)            

            router_alloc = self._alloc_type(current_as)      

            for ix in ixes_joined_by_asn:
                ix_alias = self._ASNforIXp(ix)
                members = self.__provider.getInternetExchangeMembers(ix)
                # with .gml dataset samples from larger CAIDA files,
                # it is possible that nodes list IXP presences from the full dataset
                # that aren't actually relevant for the smaller subset
                if not members:
                    continue
                # no need to create IXPs that have no members anyway
                if ix_alias not in base.getInternetExchangeIds():              
                             
                    # only create ix if it didnt already exist !!
                    #if ix not in base.getInternetExchangeIds():
                    self.__log('creating new IX, IX{}; getting prefix...'.format(ix_alias))
                    _ixp=base.createInternetExchange( ix_alias,
                                                      prefix = self.__provider.getInternetExchangePrefix(ix) ,
                                                      create_rs= False)
                    _ixp_attr = self.__provider.getInternetExchangeAttributes(ix)
                    _ixp.getNetwork().setDefaultLinkProperties(latency=_ixp_attr['latency'],
                                                               bandwidth=_ixp_attr['bandwidth'],
                                                               packetDrop=_ixp_attr['packetDrop'])

                self.__log('getting members of IX{}...'.format(ix_alias))
              

                self.__log('joining IX{} with AS{}...'.format(ix_alias, asn))
                ip_of_asn_in_ix = members[asn]
                       
                router_a = router_alloc.getRouterForIX(ix_alias)                
                router_a.updateNetwork(netname)
                router_a.joinNetwork('ix{}'.format(ix_alias), ip_of_asn_in_ix)
            
                self.__log('creating {} other ASes in IX{}...'.format(len(members.keys()), ix_alias))
                for member in members.keys():
                    self.__generate(member, emulator, depth - 1)
                   
                    if member in peers.keys():
                        # FIXME: right = peer is customer, left = peer is provider
                        r = peers[member]
                        
                        
                        # In case of Transit: A is parent      
                        #TODO: create a unique key for the link and add it to the cache
                        # before any link is created, check if its not already in the cache

                        ifs = r['ifids']
                        rightWay=r['rightWayRound']
                       # IXLinkAdded = False
                        for i,p in enumerate(ifs):
                            rel = p[2]                            
                            
                            self.__log('peering AS{} with AS{} in IX{} using relationship {}...'.format(member, asn, ix_alias, rel))
                            # which IF belongs to which AS is already sorted out by the provider!!
                            a_ifid = p[0] #if rightWay[i] else p[1]
                            b_ifid =p[1] #if rightWay[i] else p[0]
                            attr_a = self.__provider.getLinkAttributes(asn,a_ifid)
                            attr_b = self.__provider.getLinkAttributes(member,b_ifid)
                            ixa = attr_a['ixp_id']
                            ixb = attr_b['ixp_id']                                
                            assert ixa == ixb
                            if  ixa != ix:
                                continue
                            if not self.__cache_link((asn,a_ifid),(member,b_ifid),rel) :
                                self.__debug_cnt+=1
                                ix_ab_alias = self._ASNforIXp(ixa)
                                assert ix_alias==ix_ab_alias
                             
                                router_alloc_b = self._alloc_type(base.getAutonomousSystem(member))
                                router_b = router_alloc_b.getRouterForIX(ix_alias)
                                if (lat_a:=attr_a['latitude'],long_a:=attr_a['longitude'],
                                    lat_b:=attr_b['latitude'],long_b:=attr_b['longitude']):
                                    if lat_a==lat_b and long_a==long_b:
                                        router_a.setGeo(Lat=float(lat_a), Long=float(long_a))
                                        router_b.setGeo(Lat=float(lat_b), Long=float(long_b))
                                    else:
                                        raise ValueError("two routers within the same IXP ought to have the same geo-coordinates")

                                if rel == LinkType.Transit : # and  rightWay[i]
                                    # a: PARENT(provider) | b: CHILD(customer)
                                    base = emulator.getLayer('Base')
                                    
                                    #assert  not self.__provider.isCore(member)
                                    if  rightWay[i]:
                                        scion.addIxLink( ix_ab_alias,  (1, asn),(1, member),rel,                                                 
                                                 b_router=router_b.getName(),
                                                 a_router=router_a.getName(),
                                                         if_ids=(a_ifid,b_ifid))        
                                    else:
                                        scion.addIxLink( ix_ab_alias,  (1, member),(1, asn),rel,                                                 
                                                 a_router=router_b.getName(),
                                                 b_router=router_a.getName(),
                                                         if_ids=(b_ifid, a_ifid))        
                                else:
                                    scion.addIxLink( ix_ab_alias, (1, asn), (1, member),rel,
                                                      a_router=router_a.getName(),
                                                      b_router=router_b.getName(),
                                                     if_ids=(a_ifid,b_ifid))
                               # IXLinkAdded = True
                            else:
                                pass

                        # assert IXLinkAdded, f'failed to add IX link between {asn} and {member} in IXP {ix}'
                                

            for (peerasn,v) in cross_connects.items():
                for vv in v:
                    addr =vv[0]
                    linktype = vv[1]
                    ifids = vv[2]                                        

                    a_router,peer_br_name = router_alloc.getRouterForXC(ifids,peerasn)
                    a_router.updateNetwork(netname)
                    a_attr = self.__provider.getLinkAttributes(asn,ifids[0])
                    # b_attr = self.__provider.getLinkAttributes(peerasn,ifids[1])
                    # errMsg = 'inconsistent topology data file! seed does not support asymmetric links'
                    # assert haveEqualLinkProperties(a_attr,b_attr), errMsg
                    a_router.crossConnect(peerasn, peer_br_name, addr,
                                        latency=a_attr['latency'],
                                        bandwidth=a_attr['bandwidth'],
                                        packetDrop= a_attr['packetDrop'] )

                        
                    # do not add transit links in both directions
                    if linktype == LinkType.Transit:
                        if not ((1,peerasn),(1,asn),linktype ) in scion.getXcLinks():
                            scion.addXcLink((1,asn),(1,peerasn), linktype,
                                            a_router=a_router.getName(),
                                            b_router=peer_br_name )
                    else:
                        scion.addXcLink((1,asn),(1,peerasn), linktype,
                                        a_router=a_router.getName(),
                                            b_router=peer_br_name )

                self.__generate(peerasn, emulator, depth - 1)

        elif nr_prefixes > nr_joined_ixes:
            # here we have to decice which brnode shall join which net/prefix ..
            # Or create subnets of the prefix and have each brnode join one of them ?! Help
            raise NotImplementedError("this case is unimplemented")
        
        elif nr_prefixes == nr_joined_ixes:
            # maybe map each brnode to its own prefix ?!
            raise NotImplementedError("cant handle this case yet")
      


    def generate_custom(self, startAsn: int, depth: int, emu: Emulator ) -> Emulator:

        base=emu.getLayer('Base')
        assert base!=None, 'provided Emulator must contain Base Layer'
        assert emu.getLayer('Routing'), 'provided Emulator must contain Routing Layer'
        assert emu.getLayer('ScionIsd')
        assert emu.getLayer('Scion')

        base.createIsolationDomain(1)   

        self.__generate(startAsn, emu, depth) # TODO: compute an upper bound for the depth, it can default to
        return emu
        

    def generate(self, startAsn: int, depth: int) -> Emulator:
        """!
        @brief generate a new emulation.

        @param startAsn ASN to start on.
        @param depth levels to traverse.

        @returns generated emulator.
        """
        sim = Emulator()
        ospf = Ospf()        
        base = ScionBase()
        routing = ScionRouting()
        scion_isd = ScionIsd()
        scion = Scion()
        
        sim.addLayer(base)
        sim.addLayer(routing)
        sim.addLayer(scion_isd)
        sim.addLayer(scion)     
        sim.addLayer(ospf)

        
        return self.generate(startAsn, depth,sim)