from .enums import NodeRole
from .Node import Router

class ExternalRouter():
    def __init__(self, name, autonomous_system, interfaces=None):
        self.name = name
        self.autonomous_system = autonomous_system
        self.interfaces = interfaces or []
        self.router = self.autonomous_system.createRouter(name)
        asn = self.autonomous_system.getAsn()

    def add_interface(self, name, ip=None, mac=None):
        self.interfaces.append({
            "name": name,
            "ip": ip,
            "mac": mac
        })

    def joinNetwork(self, netname: str, address: str, mac=None):
        self.router.joinNetwork(netname, address)
        self.add_interface(netname, address, mac)
        return self

    def crossConnect(self, peerasn: int, peername: str, address: str, mac: str=None, MTU: int=1500):
        self.router.crossConnect(peerasn, peername, address, 0, 0, 0, MTU)
        self.add_interface(peername, address, mac)
        return self

    def getExportDir(self, base_dir):
        return f"{base_dir}/external_{self.name}"
