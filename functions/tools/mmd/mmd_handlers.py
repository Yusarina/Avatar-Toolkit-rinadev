# GPL License
# Avatar Toolkit MMD Converter - MMD Handlers Module

import bpy
from typing import Dict, List, Tuple, Optional, Any
from bpy.types import Context, Object
from mathutils import Vector, Quaternion

from ....core.logging_setup import logger
from ....core.common import get_meshes_for_armature, set_active
from ....core.mmd.translations import translateFromJp, jp_half_to_full_tuples


class MMDRootHandler:
    """Handler for MMD-specific root object operations"""
    
    @staticmethod
    def get_mmd_root(armature: Object) -> Optional[Any]:
        """Get the mmd_root property if this is an MMD model"""
        try:
            if armature.parent and hasattr(armature.parent, 'mmd_root'):
                return armature.parent.mmd_root
        except AttributeError:
            pass
        return None
    
    @staticmethod
    def backup_bone_collections(armature: Object) -> List[Dict[str, Any]]:
        """Backup bone collections before processing to prevent crashes"""
        bone_collections_backup: List[Dict[str, Any]] = []
        
        for collection in armature.data.collections:
            backup = {
                'name': collection.name,
                'is_visible': collection.is_visible,
                'bones': [bone.name for bone in collection.bones]
            }
            bone_collections_backup.append(backup)
        
        return bone_collections_backup
    
    @staticmethod
    def remove_bone_collections(armature: Object) -> int:
        """Remove bone collections (safely) and return count removed"""
        removed = 0
        
        # Get all collection names first to avoid modification during iteration
        collection_names = [c.name for c in armature.data.collections]
        for name in collection_names:
            if name in armature.data.collections:
                armature.data.collections.remove(armature.data.collections[name])
                removed += 1
        
        return removed


class BoneMorphConverter:
    """Convert MMD bone morphs to shape keys - works on Linux without mmd_tools"""
    
    @staticmethod
    def convert_bone_morphs_to_shapekeys(context: Context, armature: Object, mmd_root: Any) -> int:
        """
        Native bone morph to shape key conversion for Linux compatibility.
        
        Args:
            context: Blender context
            armature: The armature object
            mmd_root: The mmd_root property object
            
        Returns:
            Number of morphs converted
        """
        if not hasattr(mmd_root, 'bone_morphs') or len(mmd_root.bone_morphs) == 0:
            return 0
        
        mesh_objects = get_meshes_for_armature(armature)
        if not mesh_objects:
            logger.warning("No mesh objects found for bone morph conversion")
            return 0
        
        mesh = mesh_objects[0]
        set_active(mesh)
        
        # Ensure we have shape keys
        if not mesh.data.shape_keys:
            mesh.shape_key_add(name="Basis")
        
        # Collect morph names for translation
        to_translate: List[str] = []
        for morph in mmd_root.bone_morphs:
            to_translate.append(morph.name)  # Japanese name
        
        wm = context.window_manager
        current_step = 0
        wm.progress_begin(current_step, len(mmd_root.bone_morphs))
        
        # Store original bone transforms
        original_transforms: Dict[str, Dict[str, Any]] = {}
        for bone in armature.pose.bones:
            original_transforms[bone.name] = {
                'location': bone.location.copy(),
                'rotation_quaternion': bone.rotation_quaternion.copy(),
                'rotation_euler': bone.rotation_euler.copy(),
            }
        
        converted_count = 0
        
        # Process each bone morph
        for morph in mmd_root.bone_morphs:
            current_step += 1
            wm.progress_update(current_step)
            
            if not morph.data:
                continue
            
            # Apply bone transformations
            for morph_data in morph.data:
                if morph_data.bone in armature.pose.bones:
                    pose_bone = armature.pose.bones[morph_data.bone]
                    if hasattr(morph_data, 'location'):
                        pose_bone.location += Vector(morph_data.location)
                    if hasattr(morph_data, 'rotation'):
                        pose_bone.rotation_quaternion @= Quaternion(morph_data.rotation)
            
            context.view_layer.update()
            
            # Create shape key with translated name
            original_name = morph.name
            translated_name, _ = BoneMorphConverter._translate_morph_name(original_name)
            shape_key = mesh.shape_key_add(name=translated_name)
            
            converted_count += 1
            
            for bone_name, transforms in original_transforms.items():
                if bone_name in armature.pose.bones:
                    pose_bone = armature.pose.bones[bone_name]
                    pose_bone.location = transforms['location']
                    pose_bone.rotation_quaternion = transforms['rotation_quaternion']
                    pose_bone.rotation_euler = transforms['rotation_euler']
        
        wm.progress_end()
        context.view_layer.update()
        
        return converted_count
    
    @staticmethod
    def _translate_morph_name(name: str) -> Tuple[str, bool]:
        """Translate morph name from Japanese to English"""
        original = name
        
        # Convert half-width to full-width first
        for half, full in jp_half_to_full_tuples:
            name = name.replace(half, full)
        
        # Then translate using dictionary
        translated = translateFromJp(name)
        
        return translated, (translated != original)


def get_mmd_root(armature: Object) -> Optional[Any]:
    """Public function to get MMD root"""
    return MMDRootHandler.get_mmd_root(armature)
