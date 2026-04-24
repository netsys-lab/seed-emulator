from __future__ import annotations
from typing import List, Optional, Dict, Any
from .ExternalEmulatorPlugin import ExternalEmulatorPlugin


class ExternalEmulatorManager:
    """
    Manages lifecycle of external emulator integrations.
    Responsible for:
      - plugin registration
      - config generation
      - runtime startup / shutdown
    """

    def __init__(self):
        self._plugins: List[ExternalEmulatorPlugin] = []
        self._generated: List[Dict[str, Any]] = []

    def register(self, plugin: ExternalEmulatorPlugin):
        self._plugins.append(plugin)

    def get_plugin(self, external) -> Optional[ExternalEmulatorPlugin]:
        for p in self._plugins:
            if p.can_handle(external):
                return p
        return None

    def generate_all(self, externals: list, export_base_dir: str):
        """
        Generate configuration + metadata for all externals.
        """
        self._generated.clear()

        for ext in externals:
            plugin = self.get_plugin(ext)
            if plugin is None:
                raise RuntimeError(f"No plugin found for external: {ext}")

            export_dir = ext.getExportDir(export_base_dir)
            meta = plugin.generate(ext, export_dir)

            self._generated.append({
                "external": ext,
                "plugin": plugin,
                "export_dir": export_dir,
                "meta": meta
            })

        return self._generated

    def start_all(self):
        """
        Start all generated externals using plugin.start().
        """
        results = []
        for entry in self._generated:
            plugin = entry["plugin"]
            ext = entry["external"]
            export_dir = entry["export_dir"]

            code = plugin.start(ext, export_dir)
            results.append((ext.name, code))

        return results

    def stop_all(self):
        """
        Stop all generated externals.
        """
        results = []
        for entry in self._generated:
            plugin = entry["plugin"]
            ext = entry["external"]
            export_dir = entry["export_dir"]

            code = plugin.stop(ext, export_dir)
            results.append((ext.name, code))

        return results