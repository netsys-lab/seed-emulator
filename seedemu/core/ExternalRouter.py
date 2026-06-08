from .enums import NodeRole
from .Node import Router
import os

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

#        externals = emulator.getExternalComponents()
#        for ext in externals:
#            if ext.asn == asn:
#                topology["border_routers"][ext.name] = {
#                "interfaces": {
#                    iface["name"]: {
#                        "underlay": iface["ip"],
#                        "mac": iface["mac"],
#                        }
#                        for iface in ext.interfaces
#                    }
#                }
def exportScionConfig(self, output_dir):
    import os

    folder = os.path.join(
        output_dir,
        f"external_as{self.autonomous_system.getAsn()}_{self.name}"
    )

    os.makedirs(folder, exist_ok=True)

    # IMPORTANT: files are stored in self.router, not self
    for file in self.router.getFiles():
        path, content = file.get()

        if "topology" in path or "crypto" in path:
            filename = os.path.basename(path)

            if "crypto" in path:
                crypto_dir = os.path.join(folder, "crypto")
                os.makedirs(crypto_dir, exist_ok=True)
                target_path = os.path.join(crypto_dir, filename)
            else:
                target_path = os.path.join(folder, filename)

            with open(target_path, "w") as f:
                f.write(content)

    return folder