from seedemu.core import Emulator
from seedemu.core.ExternalEmulatorPlugin import ExternalEmulatorPlugin
from seedemu.core.ExternalEmulatorManager import ExternalEmulatorManager
from seedemu.layers import Base
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

    emu = Emulator()
    emu.addLayer(Base())

    # Create external
    router = ExternalRouter("hardware_router")
    router.add_interface("eth0", ip="10.0.0.1/24", mac="00:11:22:33:44:55")

    # Register external into SEED
    emu.registerExternalComponents(router)

    # Register plugin into manager
    emu._externalManager = ExternalEmulatorManager()  # ensure manager exists
    emu._externalManager.register(DummyPlugin())

    # Compile (this will now trigger external manager automatically)
    from seedemu.compiler.Docker import Docker
    compiler = Docker()

    emu.render()
    emu.compile(compiler, "output_external", override=True)

    # ---- Start externals via manager ----
    results = emu._externalManager.start_all()
    print("External start results:", results)

    print("Demo finished. Check output_external folder.")