# GPL License
# Avatar Toolkit MMD Converter - Modular Package

"""
MMD Armature Fixer Module

This package provides tools for fixing and converting MMD (MikuMikuDance) 
armatures for use with VRChat/Unity.

Note: The operator class (AvatarToolkit_OT_FixMMDArmature) is auto-discovered
and registered by auto_load.py. Only utility functions need explicit exports.
"""

# Utility functions needed by mmd_panel.py
from .validation import detect_mmd_armature
from .mmd_handlers import get_mmd_root

__all__ = [
    'detect_mmd_armature',
    'get_mmd_root',
]
