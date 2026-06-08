from seedemu.core import Emulator
from seedemu.core.ExternalEmulatorPlugin import ExternalEmulatorPlugin
from seedemu.core.ExternalEmulatorManager import ExternalEmulatorManager
#from seedemu.layers import Base
from seedemu.layers import ScionBase, ScionRouting, ScionIsd, Scion
from seedemu.layers.Scion import LinkType as ScLinkType
from seedemu.core.ExternalRouter import ExternalRouter




# ---- Plugin Example ----
class DummyPlugin(ExternalEmulatorPlugin):

    @property
    def name(self) -> str:
        return "dummy_router_plugin"

    def can_handle(self, external):
        from seedemu.core.ExternalRouter import ExternalRouter
        return isinstance(external, ExternalRouter)

    def generate(self, external, export_dir):
        import os
        import json

        os.makedirs(export_dir, exist_ok=True)

        # ---- Generate topology.json ----
        topology = {
            "router_name": external.name,
            "interfaces": external.interfaces
        }

        with open(os.path.join(export_dir, "topology.json"), "w") as f:
            json.dump(topology, f, indent=4)

        # ---- Generate start script ----
        start_script_path = os.path.join(export_dir, "start.bat")

        with open(start_script_path, "w") as f:
            f.write("@echo off\n")
            f.write("echo Starting external router...\n")
            f.write("echo Router name: " + external.name + "\n")
            f.write("echo --- TOPOLOGY CONTENT ---\n")
            f.write(f'type "{os.path.join(export_dir, "topology.json")}"\n')

        return {
            "status": "generated",
            "start_script": start_script_path
        }

    def start(self, external, export_dir):
        import subprocess
        import os

        script_path = os.path.join(export_dir, "start.bat")

        return subprocess.call(f'"{script_path}"', shell=True)

# ---- Main Execution ----
if __name__ == "__main__":

    print("=== FULL SEED EXTERNAL DEMO ===")

#    emu = Emulator()
#    emu.addLayer(Base())

    # Initialize
    emu = Emulator()
    base = ScionBase()
    routing = ScionRouting()
    scion_isd = ScionIsd()
    scion = Scion()

    # AS-150
    as150 = base.createAutonomousSystem(150)
    scion_isd.addIsdAs(1, 150, is_core=True)
    as150.createNetwork('net0')
    as150.createControlService('cs1').joinNetwork('net0')
    as150_router = as150.createRouter('br0')
    as150_router.joinNetwork('net0')
    as150_router.crossConnect(153, 'EXT_BR153', '10.50.0.2/29')

    # AS-153
    as153 = base.createAutonomousSystem(153)
    scion_isd.addIsdAs(1, 153, is_core=False)
    scion_isd.setCertIssuer((1, 153), issuer=150)
    as153.createNetwork('net0')
    as153.createControlService('cs1').joinNetwork('net0')
    as153_router = as153.createRouter('EXT_BR153')
    as153_router.joinNetwork('net0')
    as153_router.crossConnect(150, 'br0', '10.50.0.3/29')
    as153_router.setExternal(True)# 

    # Create external
    #ext = ExternalRouter("EXT_BR153", as153)
    #ext.joinNetwork('net0', '10.50.1.4', mac="00:11:22:33:44:54")
    #ext.crossConnect(150, 'br0', '10.50.0.3/29', mac="00:11:22:33:44:55")

    # Inter-AS routing
    scion.addXcLink((1, 150), (1, 153), ScLinkType.Transit)

    # Register external into SEED
    #emu.registerExternalComponents(ext)

    # Register plugin into manager
    #emu._externalManager = ExternalEmulatorManager()  # ensure manager exists
    #emu._externalManager.register(DummyPlugin())

    # Rendering
    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(scion_isd)
    emu.addLayer(scion)

    emu.render()

    # Compile (this will now trigger external manager automatically)
    from seedemu.compiler.Docker import Docker
    compiler = Docker()
    emu.compile(compiler, "output_external", override=True)

    # ---- Start externals via manager ----
    results = emu._externalManager.start_all()
    print("External start results:", results)

    print("Demo finished. Check output_external folder.")


