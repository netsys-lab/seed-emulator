from __future__ import annotations
from seedemu.core import Node, Emulator, Layer
from seedemu.core.enums import NetworkType,NodeRole
from typing import Set, Dict, List, Tuple

StaticTemplates: Dict[str,str] = {}
StaticTemplates['body'] ="""
    debug all;
    ipv4 {
        table t_static;
        import all;
        export none;
    };
"""



'''
    ipv4 {
        table t_static; # default is the fst table of given nettype (ipv4) master4
        import all; # from proto to table (default: all)
        export none; # from table to protocol (default: none)
    };
'''

class StaticRouting(Layer):
    """
    a replacement for dynamic intra domain routing i.e. with OSPF,
    in case an AS has only a single network.
    Works with BIRD routing daemon.
    """

    def __init__(self):
        super().__init__()
        self.addDependency('Routing',False,False)

    def getName(self) -> str:
        return 'StaticRouting'
    
    def render(self,emulator: Emulator):
        reg = emulator.getRegistry()

        for ((scope, type, name), obj) in reg.getAll().items():
            if type != 'rnode': continue
            router: Node = obj
            router.addTable('t_static')
            
            router.addTablePipe('t_static') # from t_static to master4 (import none from dst, but export all to dst from src)
            # TODO: also add loopback addresses of neighbors in IXps ?!            
            body = StaticTemplates['body']

            net = [ i.getNet() for i in router.getInterfaces() if i.getNet().getType()==NetworkType.Local ][0]
            body += '   route {} via "{}"; \n'.format( net.getPrefix(), net.getName() )
            # for each sibling router of 'rnode' in net0 
            # add a default route to the siblings loopbackaddr
            for sib in reg.getByType(str(router.getAsn()),'rnode'):
                if sib!=router:
                    body += '   route {}/32 via {};\n'.format(sib.getLoopbackAddress(), sib.getIPAddress()) #  dev "{}"  , 'net0'
           
            router.addProtocol('static','static1', body )

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'StaticRoutingLayer\n'
        return out
    

class HardwiredRouting(Layer):
    """
    a replacement for dynamic intra domain routing i.e. with OSPF,
    in case an AS has only a single network.
    Manually sets up 'ip route's without any routing daemon.
    """

    def __init__(self):
        super().__init__()
        self.addDependency('Routing',False,False)

    def getName(self) -> str:
        return 'HardwiredRouting'
    
    def render(self,emulator: Emulator):
        reg = emulator.getRegistry()

        for ((scope, type, name), obj) in reg.getAll().items():
            if type != 'rnode': continue
            router: Node = obj
          
            # TODO: also add loopback addresses of neighbors in IXps ?!                        
            routes = []

            # for each sibling router of 'rnode' in net0 
            # add a default route to the siblings loopbackaddr
            for sib in reg.getByType(str(router.getAsn()),'rnode'):
                if sib!=router:
                    routes.append( 'ip route add {}/32 via {}'.format(sib.getLoopbackAddress(), sib.getIPAddress()) ) #  dev "{}"  , 'net0'

            for cmd in routes:
                router.appendStartCommand(cmd)


    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'HardwiredRoutingLayer\n'
        return out