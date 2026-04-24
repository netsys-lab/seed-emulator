class ExternalRouter:
    def __init__(self, name, interfaces=None):
        self.name = name
        self.interfaces = interfaces or []

    def add_interface(self, name, ip=None, mac=None):
        self.interfaces.append({
            "name": name,
            "ip": ip,
            "mac": mac
        })

    def getExportDir(self, base_dir):
        return f"{base_dir}/external_{self.name}"