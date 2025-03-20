# __init__.py
from .AzimuthTool import AzimuthToolPlugin

def classFactory(iface):
    return AzimuthToolPlugin(iface)
