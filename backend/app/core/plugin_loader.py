import importlib
import pkgutil
import inspect
import os
from typing import List, Type
from app.core.plugin_interface import BasePlugin

class PluginLoader:
    def __init__(self, plugin_dir: str):
        self.plugin_dir = plugin_dir
        self.plugins: List[BasePlugin] = []

    def load_plugins(self) -> List[BasePlugin]:
        """
        Dynamically discover and load plugins from the specified directory.
        """
        self.plugins = []
        
        # Convert path to module dotted path (app.plugins...)
        # This assumes the app structure: backend/app/plugins
        # We need to walk the directory
        
        # For simplicity in this v1, we will just scan the builtins directly
        # and any user plugins in the plugins dir.
        
        # Let's assume absolute paths are tricky with importlib, 
        # so we rely on relative imports from the 'app' package.
        
        base_package = "app.plugins"
        
        # Walk through the packages
        self._scan_package(base_package)
        
        print(f"Loaded {len(self.plugins)} plugins: {[p.name for p in self.plugins]}")
        return self.plugins

    def _scan_package(self, package_name: str):
        try:
            package = importlib.import_module(package_name)
        except ImportError as e:
            print(f"Could not import package {package_name}: {e}")
            return

        for _, name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            try:
                module = importlib.import_module(name)
                self._scan_module(module)
            except Exception as e:
                print(f"Error loading module {name}: {e}")

    def _scan_module(self, module):
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, BasePlugin) and 
                obj is not BasePlugin):
                
                # Instantiate the plugin
                try:
                    plugin_instance = obj()
                    self.plugins.append(plugin_instance)
                except Exception as e:
                    print(f"Error instantiating plugin {name}: {e}")
