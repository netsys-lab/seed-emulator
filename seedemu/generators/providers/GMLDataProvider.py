from typing import List, Dict,Any,Tuple
from sys import stderr
from . import  DataProvider
from toolz.dicttoolz import *
from seedemu.layers.Scion import LinkType,IA
from seedemu.core import ScionMcastCapableAutonomousSystem
import networkx as nx
import numpy as np


def bfs_traversal(T,s):
    """
    to BFS traversal of the tree T starting from root 's'
    return Tuple[traversal-sequence as list of node-ids , 
                dictionary with list of direct children for each node ]
    """
 
    # Mark all the vertices as not visited
    visited = { n: False for n in T.nodes() }

    sequence = []
    children = { n: {'ifs': [] } for n in T.nodes() }
 
    # Create a queue for BFS
    queue = []
 
    # Mark the source node as
    # visited and enqueue it
    queue.append(s)
    visited[s] = True
 
    while queue:
 
        # Dequeue a vertex from
        # queue and print it
        s = queue.pop(0)

        sequence.append(s)
 
        # Get all adjacent vertices of the
        # dequeued vertex s.
        # If an adjacent has not been visited,
        # then mark it visited and enqueue it
        for i in T.neighbors(s):
            if visited[i] == False:
                queue.append(i)
                visited[i] = True
                children[s]['ifs'].append(i)

    return sequence, children

class GMLDataProvider(DataProvider):
    """!
    @brief data source for the topology generator.
    It is really just a wrapper around an networkx MultiGraph
    that contains ASes and their various interconnections,
    and at which IXp they happen.
    """
    _topofile: str
    _core_asn: int = -1

    def _setIfId(self, ia: IA, ifid: int ):
        """
        This has to be the exact same impl as in Scion Layer.
        So better refactor these two methods into a Mixin
        """
        ifs = set()
        if ia in self.__if_ids_by_as:
            ifs = self.__if_ids_by_as[ia]

        v = ifid in ifs
        ifs.add(ifid)    
        self.__if_ids_by_as[ia] = ifs
        return v
    
    def getNextIfId(self, ia: IA ) -> int:
        """
        This has to be the exact same impl as in Scion Layer
        """
        ifs = set()
        if ia in self.__if_ids_by_as:
            ifs = self.__if_ids_by_as[ia]

        if not ifs:
            ifs.add(0)
            return 0

        curr = -1
        last = -1

        def hasSpaceToLeft(i,curr,last):
            curr=i
            return curr-last>1        
        
        '''
        has_space_to_left = lambda i: (
        curr := i,
        curr-last>1
        )'''

        for i in ifs:
            if hasSpaceToLeft(i,curr,last):
                ifs.add(last+1) 
                return last+1
            else:
                last=i

        ifs.add(last+1)
        return last+1

    def getASes(self) -> List[int]:
        """
        return list of all ASes in the dataset.
        """
        return list( map(lambda n: self._aliasASN(n), self._graph.nodes ) )
    
    def getAttributes(self, _asn: int)->Dict[str,any]:
        
        real_asn = self._unaliasASN(_asn)
        return {'type': ScionAutonomousSystem ,
                'mhfa': self.getMHFA(_asn),
                'latency': 0,
                'bandwidth':0,
                'mtu': 1500,
                'packetDrop': 0,
                'note': f'{real_asn}'                      
                } # TODO: add 'features/confiiguration': Dict[str,str] here 

    # maybe also return the remote AS to which the Interface points
    # or alternatively provide another method on the data-provider,
    # that allows for manual translation:  IF-Id of AS -> remote AS

    # Maybe add a filter argument to this method:
    # (actually it would be consequent to replace the _asn argument altogether with a filter)
    # (The filter would accept an (aliased) edge as input )
    # i.e. only return Interfaces, realized on a certain IXP-id
    # or only Interfaces leading to a given remote AS
    def getASInterfaces(self, _asn: int) ->List[int]:
        """
        @param asn Alias ASN
        """

        asn = self._unaliasASN(_asn)
        ifids = nx.get_edge_attributes(self._graph,'if_ids')
        dirs = nx.get_edge_attributes(self._graph,'direction')
        
        edges =  [ ee for ee in self._graph.edges if int(ee[0])==int(asn) or int(ee[1])==int(asn) ] 
      
        interfaces = []
        for e in edges: 
            ids = ifids[e] if (e in ifids) else ifids[ (e[1],e[0],e[2]) ]
            dir = dirs[e] if (e in dirs) else dirs[ (e[1],e[0],e[2]) ]
            interfaces .append( ids[0] if int(dir[0])==int(asn) else ids[1] )

        assert 0 not in interfaces
        return interfaces

    def _makeGraphScionCapable(self):
        """
        SCION PCB are only propagated through transit links from parent to children.
        So for a set of scion ASes S with a single Core AS C in S,
        there must exist a directed spanning tree of transit links ,
        connecting the members of S , rooted at C.
        Most probably a random sample from a CAIDA dataset will not fullfill this property.
        This method converts suitable peering links into transit links 
        and changes direction of existing transit links, 
        so that PCBs reach all ASes in S.
        """

        G = nx.MultiGraph()
        G.add_nodes_from(self._graph.nodes(data=True))
        transit_edges = [e for e in self._graph.edges(keys=True,data=True) if e[3]['rel'] == 'customer']
        G.add_edges_from(transit_edges)

        # remove later
        for x in zip(G.nodes(data=True),self._graph.nodes(data=True)):
            assert x[1] == x[0]
        # def _min_linkage_all(A,B): # returns all shortest links, not just one

        def _min_linkage(A,B) -> Tuple[int,List[int]]: # length, path
            """
            A and B are conn components in G
            Now find the minimal shortest path between any two nodes x in a and y in b in the super graph.
            """
            res = (99999,[])
            for x in A:
                for y in B:
                    p = nx.shortest_path(self._graph,x,y)
                    cost = len(p)
                    if cost < res[0]:
                        res = (cost,p)
                        if cost ==2:
                            # there is just no shorter path, then start-end
                            break
                else:
                    continue  # only executed if the inner loop did NOT break
                break  # only executed if the inner loop DID break
            return res

        grafted_edges = []  # list of peering edges which are grafted to transit links
        # find and connect all components in G (fst is biggest)
        cns =  sorted(nx.connected_components(G), key=len, reverse=True)
     
        conns = cns

        while len(conns) != 1:
            a = conns.pop() 
            res = (99999,[],0)
            for i,b in enumerate(conns):
                c = _min_linkage(a,b)
                if c[0]< res[0]:
                    res = (c[0],c[1],i)
                    if res[0] == 2:
                        break
            else:
                continue
            
            # merge a,b and any intermediate nodes 'c' on the path

            # check that c is not already in any component other than a,b (that has more members than just c)
            b = conns.pop(res[2])
            if res[0]>2:
                for x in res[1][1:1:-2]:
                    for c in conns:
                        if x in c:
                            assert len(c)==1
                            conns.pop( conns.index(c))
                            # TODO: add link a-x  x-b  to G
                            #   add x to  merged componend a+b+x
                            assert False 
            
            d = a.union( b)
            # convert peering edge to transit
            e = [ ed for ed in self._graph.edges(keys=True,data=True)  if ed[3]['rel']=='peer' and ed[0] ==res[1][0] and ed[1]==res[1][-1] or  ed[1] ==res[1][0] and ed[0]==res[1][-1]][0]

            grafted_edges.append(e)
            e[3]['rel'] = "customer"
            G.add_edges_from([e])
            conns = sorted( conns + [d], key=len, reverse=True)

        assert len(conns[0]) == len(G.nodes())
        assert  nx.is_connected(G)
        assert nx.is_tree(G)

        # TODO: step I    compute spanning tree ST in G
        #                prune any transit edges not in ST to peering links
        #       step II    call computeCoreAS()
        #       step II   do BFS traversal of ST starting from core AS
        #                flip any edges you traverse against the Parent-Child direction ( swap their 'direction' and 'if_ids' edge attributes in self._graph )

        # this is probably too complicated:
        # instead just prune all transit links there are in the dataset sample to peering links.
        # then select a core AS according to betweenness centrality
        # then compute spanning tree
        #  BFS traverse spanning tree rooted at Core AS , graft traversed edges to transit links,
        # and correct their direction and if_ids edge attributes to match the direction of traversal.
    def makeSCIONCapable(self):
        

        _core = self._computeCoreAS()

        T = nx.minimum_spanning_tree(self._graph)
        core = self._unaliasASN(_core)
        seq,childs = bfs_traversal(T, core)
        relations = nx.get_edge_attributes(self._graph,'rel')
        direct = nx.get_edge_attributes(self._graph,'direction')
        ifs = nx.get_edge_attributes(self._graph,'if_ids')

        e = [ ed for ed in self._graph.edges(keys=True,data=True)  ] #if ed[3]['rel']=='customer'

#        self._graph.remove_edge(e[0],e[1],e[2])
        for ex in e:
            ex[3]['rel'] = "peer"
            if (ex[0],ex[1],ex[2]) in relations:
                relations[(ex[0],ex[1],ex[2])] = 'peer'
            else:
                relations[(ex[1],ex[0],ex[2])] = 'peer'
 #       self._graph.add_edges_from([e])

        def modify_edge(e,n,relations,direct,ifs):
                """
                'n' is the current node in the tree traversal,
                and 'e' is the edge that we are about to traverse next.
                If the direction of 'e' is against this, it gets flipped.
                Moreover if the LinkType of the edge is 'peer' is is grafted to 'customer'
                """
                e[3]['rel'] = 'customer'
                if (e[0],e[1],e[2]) in relations:
                    relations[(e[0],e[1],e[2])]='customer'
                else:
                    relations[(e[1],e[0],e[2])]='customer'
                    
                #dir = e[3]['direction']
                dir = []
                if (e[0],e[1],e[2]) in direct:
                    dir = direct[(e[0],e[1],e[2])]
                else:
                    dir = direct[(e[1],e[0],e[2])]

                # link is traversed against edge direction
                if dir[0] != int(n):
                    assert dir[1] == int(n)
                    # change edge direction

                    new_direction = list( reversed( e[3]['direction']) )
                    new_if_ids = list( reversed( e[3]['if_ids']) )
                    e[3]['if_ids'] = new_if_ids
                    e[3]['direction'] = new_direction

                    if (e[0],e[1],e[2]) in direct:
                        direct[(e[0],e[1],e[2])]= new_direction
                    else:
                        direct[(e[1],e[0],e[2])]= new_direction

                    
                    if (e[0],e[1],e[2]) in ifs:
                        ifs[(e[0],e[1],e[2])]= new_if_ids
                    else:
                        ifs[(e[1],e[0],e[2])]= new_if_ids

        for n in seq:
            children = childs[n]['ifs']
            for c in children:
                edgs = [ ed for ed in self._graph.edges(keys=True,data=True) if  (ed[0]==n and ed[1]==c) or (ed[1]==n and ed[0]==c) ]
                e = edgs[0] # it is sufficient to have one transit edge in the right direction, for beacons to propagate
                
                modify_edge(e,n,relations,direct,ifs)
                
        et = [ ed for ed in self._graph.edges(keys=True,data=True)  if ed[3]['rel']=='customer']
        assert len(et)>0

        # TODO: change all peerings links of the core AS to transit links
        ecp = [ ed for ed in self._graph.edges(keys=True,data=True) if ( (ed[0]==core ) or (ed[1]==core ) ) ] # and  ed[3]['rel']=='peer' 
        for eep in ecp:

            modify_edge(eep,core,relations,direct,ifs)

        nx.set_edge_attributes(self._graph,direct,'direction')
        nx.set_edge_attributes(self._graph,ifs,'if_ids')
        nx.set_edge_attributes(self._graph,relations,'rel')

    def __init__(self, topofile: str):
        """
        @brief reads the topology file that is to be used
        """
        self._topofile = topofile
        self._graph = nx.read_gml(topofile)
        self.__if_ids_by_as = {}
        self._mhfas = {}

        self._mapping = { k: i+2 for i,k in enumerate( list( self._graph.nodes() ) ) }

        print( self._mapping)

        nx.relabel_nodes(self._graph, self._mapping )

        #self._makeGraphScionCapable()
        self.makeSCIONCapable()

    def _computeCoreAS(self) -> int:
            
        if self._core_asn == -1:
            btwn = keymap( lambda a: self._aliasASN(a), nx.betweenness_centrality(self._graph) )
            keys = list(btwn.keys())
            values = list(btwn.values())
            sorted_value_index = np.argsort(values)
            # ATTENTION: this procedure could select an AS with peering links from the dataset,
            # but core ASes can't have those
            # return keys[ sorted_value_index[-1] ]
        
            #sorted_btwn = {keys[i]: values[i] for i in sorted_value_index}
            # return sorted_btwn[-1]

            # try ASes in descending order or btwn-centrality and select the fst
            # that is eligible (has no peering links)
            for i in range(len(keys)):
                _as = keys[sorted_value_index[-1-i]]
                v = { r[2]  for x in self.getPeers(_as).values() for r in  x['ifids'] }
                
                #if LinkType.Peer not in v:
                self._core_asn = _as
                break

            assert self._core_asn!=-1, 'unable to select Core AS in provided dataset. Its probably trash'

    
        return self._core_asn
        
            

    def getCertIssuer(self, asn: int ) ->int:
        """
        @param asn Alias ASN
        """

        assert not self.isCore(asn) # or return 'asn' if it is a Core AS itself

        # return the first best Core AS that asn is connected with
        #candidates = [ k for (k,v) in self.getPeers(asn).items() if v == LinkType.Transit and ( LinkType.Peer not in self.getPeers(k).values() ) ]
        #if len(candidates)>0:
        #    return candidates[0]
        #else:
        return self._computeCoreAS()
      
    def isCore(self, asn: int )-> bool:
        """
        @brief return whether the AS with this ASN is a CORE AS 
        """

        types = nx.get_node_attributes(self._graph, "type")
        if types:
            assert len(types.keys() ) == len(self._graph.nodes()), 'AS type attribute has to be specified for all nodes in the dataset'
            if asn in  types:
                return types[asn] == "core"
            else:
                return False
        else:
            # if the graph has no 'type's specified for nodes,
            # just chose the one with the highest centrality to be a core AS
           
            return asn == self._computeCoreAS()



 
     # TODO:  also add IXP_ID if known here and remote_IF_ID
    def getLinkAttributes(self, _asn: int , if_id: int):
        """
        @brief return attributes such as Geo-Location, Bandwidth, LinkType,
        Latency for staticInfoConfig.json that gets included
        in PCB static metadata extension

        @param asn alias ASN
        """
        assert if_id != 0
        asn = self._unaliasASN(_asn)
        _as = self._graph.nodes()[asn]
        
        
         
        # from_id = nx.get_edge_attributes(self._graph, 'if_ids') # not present in .gml :(
        lat = nx.get_edge_attributes(self._graph, 'latitude')
        long = nx.get_edge_attributes(self._graph, 'longitude')
        if_ids = nx.get_edge_attributes( self._graph, 'if_ids')
        ixp_ids = nx.get_edge_attributes( self._graph, 'ixp_id')
        dirs = nx.get_edge_attributes( self._graph, 'direction')

        attrib = {'latency': 0,
                  'bandwidth': 0,
                  'packetDrop': 0,
                  'mtu': 0}
        for e in self._graph.edges(asn,keys=True): #[ee for ee in self._graph.edges if ee[0]==asn or ee[1]==asn ]:
           
           # _if = from_ifid[e] if asn == e[0] else to_ifid[e]

            ifids = if_ids[e] if ( e in if_ids) else if_ids[(e[1],e[0],e[2]) ]
            dir = dirs[e] if (e in dirs) else dirs[ (e[1],e[0],e[2]) ]
            _if  = ( ifids[0] if int(dir[0])==int(asn) else ifids[1] ) 
            

            if _if == if_id:
                attrib['latitude'] = lat[e] if ( e in lat) else lat[(e[1],e[0],e[2]) ]
                attrib['longitude'] = long[e] if ( e in long ) else long[(e[1],e[0],e[2]) ]
                attrib['ixp_id'] = ixp_ids[e] if ( e in ixp_ids ) else ixp_ids[(e[1],e[0],e[2]) ]
                break
        assert attrib
        return attrib

    def getName(self) -> str:
        """!
        @brief Get name of this data provider.

        @returns name of the layer.
        """
        return "GMLDataProvider({})".format(self._topofile)

    def getPrefixes(self, asn: int) -> List[str]:
        """!
        @brief Get list of prefixes announced by the given ASN.
        @param asn asn.

        @returns list of prefixes.        
        """
        return ["auto"]

 # why not add the Id of the IX where they peer here
 # Also why not add a 'count' field in the result here 
 #(its possible to have several links of the same type between two ASes in the same IXP)

 # use Dict[] as value type in the result dict. With i.e. 'count' , 'ifids' as keys
 # or better make the result dict have the IFIDs as keys and 'rel' as value,
 # 'count' can then be deduced from the length of the result dict.
 # The keys of the result dict must be equal to what is returned by getASInterfaces()
    def getPeers(self, _asn: int) -> Dict[int, Dict[str,Any] ]:
        """!
        @brief Get a dict of peer ASNs of the given ASN.
        @param asn alias ASN.

        @returns dict where key is asn and value is peering relationship.
        If the relationship is Transit, this means that 'asn' is a provider to its peer.
        """
        asn = self._unaliasASN(_asn)
        peer_ases = {} # return value that maps ASN of peer ASes to dict of link properties like InterfaceIDs and LinkType
        peering_relations = nx.get_edge_attributes(self._graph, 'rel')
        ifids = nx.get_edge_attributes(self._graph, 'if_ids')
        edge_directions = nx.get_edge_attributes(self._graph,'direction')
        # note that all nx.edge_     attribute maps have the same set of keys (edge tuples)
        
        for edge in self._graph.edges(asn,keys=True):
            assert edge[0] == asn
            peer_asn = edge[1]

            rrel = ""
            d ={} # currently has keys 'ifids' and 'rightWayRound'
                  # the latter is only relevant for transit links, to distinguish who is customer/provider
                  # the interfaces in 'ifids' will always be in the correct sequence: (A_id,B_id if) the edge is (A,B)
            dir=()
            
            if edge in peering_relations:
                rrel = peering_relations[edge]
                dir = edge_directions[ edge ]              
            else:
                edge =(peer_asn,asn,edge[2])
                rrel = peering_relations[edge]
                dir = edge_directions[ edge ]                
                assert  rrel == "customer" or rrel == "peer" # why not core ?!
            if peer_asn not in peer_ases:                
                peer_ases[peer_asn] = { 'ifids': [] ,'rightWayRound': []}                
            d = peer_ases[ peer_asn]

            if rrel == "core":      
                                                                                    
                            if int(dir[0])==int(asn):
                                 d['ifids'].append( (ifids[edge][0],ifids[edge][1],LinkType.Core) )
                                 d['rightWayRound'].append(True)
                            else:
                                 d['ifids'].append( (ifids[edge][1],ifids[edge][0],LinkType.Core))
                                 d['rightWayRound'].append(False)                                                         

            elif rrel == "customer":
                    # TODO FIXME: what is the semantics in caida datasets ?! 
                    #A is_customer_of B     or    A has_customer B 
                    # By this implementation it becomes  the second.
                                   
                    
                    if int(dir[0])==int(asn):                        
                            # assert d['rel'] == LinkType.Transit , "cannot mix Transit and peering links between the same two ASes {} -  {}".format(asn,peer_asn)
                            d['ifids'].append( (ifids[edge][0],ifids[edge][1],LinkType.Transit) ) # II
                            d['rightWayRound'].append(True)                     
                    else:                         
                            peer_ases[peer_asn] = { 'ifids': [], 'rightWayRound': [] }                            
                            d['ifids'].append( (ifids[edge][1],ifids[edge][0],LinkType.Transit))
                            d['rightWayRound'].append(False)

            elif rrel == "peer":                               
                                                
                            if int(dir[0])==int(asn):
                                 d['ifids'].append( (ifids[edge][0],ifids[edge][1],LinkType.Peer) ) # III
                                 d['rightWayRound'].append(True)
                            else:
                                 d['ifids'].append( (ifids[edge][1],ifids[edge][0],LinkType.Peer)) # IV
                                 d['rightWayRound'].append(True)
                        
            else:
                assert False, "invalid Value of LinkType"
            peer_ases[ peer_asn] =d                  
        assert peer_ases, "AS cannot be isolated node without peers"
        assert asn not in peer_ases, "ASes cannot have self loops"
        aliased_peer_ases = keymap( lambda k: self._aliasASN(k), peer_ases)
        return aliased_peer_ases
    
    def _aliasASN(self,asn) -> int:
        return self._mapping[asn]
    
    def _unaliasASN(self, asn) -> int:
        return list(self._mapping.keys())[ list(self._mapping.values()).index(asn) ]

    def getInternetExchanges(self, _asn: int) -> List[int]:
        """!
        @brief Get list of internet exchanges joined by the given ASN.
        @param asn alias ASN.

        @returns list of tuples of internet exchange ID. Use
        getInternetExchangeMembers to get other members.
        """
        asn = self._unaliasASN(_asn)
        ixps_by_asn = nx.get_node_attributes(self._graph, 'ixp_presences')
        joined_ixps =  ixps_by_asn[ asn ]

        ixps = nx.get_edge_attributes(self._graph, 'ixp_id')
        ixpsForAS = set()
        for edge in self._graph.edges(keys=True): # edge (u,v)   ixps (u,v, z)
             if (  asn == edge[1] or  asn == edge[0] ) :
                 ixpid = ixps[edge]
                 ixpsForAS.add(ixpid)

        assert ixpsForAS.issubset(joined_ixps)

        return ixpsForAS

# add from IFID here ?! or Tuple[from_ifdi, to_if_id ]
    def getInternetExchangeMembers(self, ix_id: int) -> Dict[int, str]: 
        """!
        @brief Get internet exchange members for given IX ID.
        @param id internet exchange ID provided by getInternetExchanges.

        @returns dict where key is ASN and value is IP address in the exchange.
        value can also be 'auto' - > it will be used as an argument to Node::joinNetwork()
        Note that if an AS has multiple addresses in the IX, only one should be
        returned.
        """
        asn2ip = dict()
        ixps = nx.get_edge_attributes(self._graph, 'ixp_id')

        # TODO: this is stupid. instead of iterating over the edges, iterate over the ixp map. There are by far less ixps than edges !!

        for edge in self._graph.edges(): # edge (u,v)   ixps (u,v, z)
            candidates = {k: v for k, v in ixps.items() if ( k[0]==edge[0] and k[1] == edge[1] or k[0]==edge[1] and k[1] == edge[0] ) and v == ix_id }
            
                        
            #if ixps[edge]  == ix_id:
            if len(candidates) > 0:
                if edge[0] not in asn2ip:
                    asn2ip[edge[0]] = "auto"

                if edge[1] not in asn2ip:
                    asn2ip[edge[1]] = "auto"

        ipForAsnInIXP=dict()
        for edg,v in ixps.items():
            if v==ix_id:
                ipForAsnInIXP[edg[0]] = "auto"
                ipForAsnInIXP[edg[1]] = "auto"


        # assert len(asn2ip) > 0 
        # with CAIDA this usually means that 'ix_id' is some non-existent invalid Ix id
        # However with .gml dataset samples from a bigger CAIDA file,
        # it is possible that ASes have presences in IXPs in the full caida set,
        # but the subset of the .gml sample contains no edges,
        # that are realized in that IXP
        assert len(ipForAsnInIXP) == len(asn2ip), 'this cant be'

        return keymap( lambda k: self._aliasASN(k) , asn2ip)

    def getInternetExchangePrefix(self, id: int) -> str:
        """!
        @brief Get internet exchange peering lan prefix for given IX ID.
        @param id internet exchange ID provided by getInternetExchanges.

        @returns prefix in cidr format.
        used for Base::createInternetExchange() by the default generator  and can be 'auto'
        """
        return "auto"   # only possible if there are less than 255 ASes and Ixps

    def _log(self, message: str):
        """!
        @brief Log to stderr.
        """
        print("==== {}CaidaDataProvider: {}".format(self.getName(), message), file=stderr)
