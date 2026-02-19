import sys
from pathlib import Path

tailor_path = Path(__file__).resolve().parent.parent.parent
print(f"Tailor path: {tailor_path}")
sys.path.insert(0, str(tailor_path))

try:
    import sidecar

    print("Successfully imported sidecar")
    print(f"sidecar file: {sidecar.__file__}")
except ImportError as e:
    print(f"Failed to import sidecar: {e}")

try:
    from sidecar.api.plugin_base import PluginBase

    print("Successfully imported PluginBase")
except ImportError as e:
    print(f"Failed to import PluginBase: {e}")
