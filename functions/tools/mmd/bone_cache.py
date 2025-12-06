# GPL License
# Avatar Toolkit MMD Converter - Bone Cache Module

from typing import Dict, List, Optional
from bpy.types import Object

from ....core.dictionaries import simplify_bonename


class BoneCache:
    """Lightweight cache system for bone lookups to improve performance"""
    
    def __init__(self, armature: Object):
        self.armature = armature
        self.bone_name_map: Dict[str, str] = {}  
        self.bone_parent_map: Dict[str, Optional[str]] = {}  
        self.bone_children_map: Dict[str, List[str]] = {}  
        self._build_caches()
    
    def _build_caches(self) -> None:
        """Build all caches"""
        # Build name lookup cache
        for bone in self.armature.data.bones:
            self.bone_name_map[bone.name.lower()] = bone.name
            
            # Build parent map
            self.bone_parent_map[bone.name] = bone.parent.name if bone.parent else None
            
            # Build children map
            if bone.parent:
                parent_name = bone.parent.name
                if parent_name not in self.bone_children_map:
                    self.bone_children_map[parent_name] = []
                self.bone_children_map[parent_name].append(bone.name)
    
    def find_bone_by_name(self, name: str) -> Optional[str]:
        """Find bone by name with case-insensitive matching"""
        return self.bone_name_map.get(name.lower())
    
    def find_bone_by_simplified_name(self, name: str) -> Optional[str]:
        """Find bone using simplified name (lowercase, no spaces/underscores/dots)"""
        simplified = simplify_bonename(name)
        for bone_name in self.bone_name_map.values():
            if simplify_bonename(bone_name) == simplified:
                return bone_name
        return None
    
    def get_parent(self, bone_name: str) -> Optional[str]:
        """Get parent bone name"""
        return self.bone_parent_map.get(bone_name)
    
    def get_children(self, bone_name: str) -> List[str]:
        """Get list of child bone names"""
        return self.bone_children_map.get(bone_name, [])
    
    def get_bone_chain(self, bone_name: str) -> List[str]:
        """Get chain of bones from root to this bone"""
        chain = [bone_name]
        current = bone_name
        while self.bone_parent_map.get(current):
            parent = self.bone_parent_map[current]
            chain.insert(0, parent)
            current = parent
        return chain
    
    def clear_cache(self) -> None:
        """Clear all cached data to prevent memory leaks"""
        self.bone_name_map.clear()
        self.bone_parent_map.clear()
        self.bone_children_map.clear()
        self.armature = None
