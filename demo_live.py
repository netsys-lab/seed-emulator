from seedemu.core.ExternalEmulatorManager import ExternalEmulatorManager
from seedemu.core.ExternalEmulatorPlugin import ExternalEmulatorPlugin

class DummyPlugin(ExternalEmulatorPlugin):
    name = "dummy"
	
    def generate (self, emulator):
            print ("[DummyPlugin] Generating Config")
	
    def start_commands(self):
            return ["echo [DummyPlugin] External emulator started"]

    def can_handle(self, *args, **kwargs):
          return True
    
if __name__ == "__main__":
    manager = ExternalEmulatorManager()
    
    plugin = DummyPlugin()
    manager.register(plugin)
    
    print("Registered plugins:", manager._plugins)
    
    manager.generate_all("output")

    print("Collected start commands:", manager.get_start_commands())
    
    manager.start_all()