# GPL License
# Avatar Toolkit MMD Converter - Final Cleanup (Phase 12)

import bpy
from typing import Dict, List, Set, Optional
from bpy.types import Context, Object

from ....core.logging_setup import logger
from ....core.common import (
    get_meshes_for_armature,
    set_active,
)


def delete_merged_bones(context: Context, armature: Object,
                        bones_to_delete: List[str]) -> int:
    """
    Delete bones that have been merged and are no longer needed.
    
    Args:
        context: Blender context
        armature: The armature object
        bones_to_delete: List of bone names to delete
        
    Returns:
        Number of bones deleted
    """
    if not bones_to_delete:
        return 0
    
    deleted_count = 0
    
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        edit_bones = armature.data.edit_bones
        
        for bone_name in bones_to_delete:
            if bone_name in edit_bones:
                bone = edit_bones[bone_name]
                
                # Reparent children to this bone's parent before deleting
                parent = bone.parent
                for child in list(bone.children):
                    child.parent = parent
                
                edit_bones.remove(bone)
                deleted_count += 1
                logger.debug(f"Deleted merged bone: {bone_name}")
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
    except Exception as e:
        logger.warning(f"Error deleting merged bones: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
    
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} merged bones")
    
    return deleted_count


def fix_bone_parenting_for_unity(context: Context, armature: Object) -> int:
    """
    Fix bone parenting to match Unity/VRChat humanoid requirements.
    
    Expected hierarchy:
    - Hips (root)
      - Spine
        - Chest
          - (UpperChest)
            - Neck
              - Head
                - Eye_L, Eye_R
            - Shoulder_L, Shoulder_R
              - UpperArm_L/R
                - LowerArm_L/R
                  - Hand_L/R
                    - Fingers...
      - UpperLeg_L, UpperLeg_R
        - LowerLeg_L/R
          - Foot_L/R
            - Toes_L/R
    
    Returns:
        Number of bones reparented
    """
    reparented_count = 0
    
    # Define expected parent-child relationships
    expected_parents = {
        # Spine chain
        'Spine': 'Hips',
        'Chest': 'Spine',
        'UpperChest': 'Chest',
        'Neck': ['UpperChest', 'Chest'],  # UpperChest preferred, Chest fallback
        'Head': 'Neck',
        
        # Eyes
        'Eye_L': 'Head',
        'Eye_R': 'Head',
        'LeftEye': 'Head',
        'RightEye': 'Head',
        
        # Left arm
        'Shoulder_L': ['UpperChest', 'Chest'],
        'UpperArm_L': 'Shoulder_L',
        'LowerArm_L': 'UpperArm_L',
        'Hand_L': 'LowerArm_L',
        
        # Right arm
        'Shoulder_R': ['UpperChest', 'Chest'],
        'UpperArm_R': 'Shoulder_R',
        'LowerArm_R': 'UpperArm_R',
        'Hand_R': 'LowerArm_R',
        
        # Left leg
        'UpperLeg_L': 'Hips',
        'LowerLeg_L': 'UpperLeg_L',
        'Foot_L': 'LowerLeg_L',
        'Toes_L': 'Foot_L',
        
        # Right leg
        'UpperLeg_R': 'Hips',
        'LowerLeg_R': 'UpperLeg_R',
        'Foot_R': 'LowerLeg_R',
        'Toes_R': 'Foot_R',
    }
    
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        edit_bones = armature.data.edit_bones
        
        for bone_name, expected_parent in expected_parents.items():
            if bone_name not in edit_bones:
                continue
            
            bone = edit_bones[bone_name]
            
            # Handle list of possible parents (first available wins)
            if isinstance(expected_parent, list):
                parent_bone = None
                for parent_name in expected_parent:
                    if parent_name in edit_bones:
                        parent_bone = edit_bones[parent_name]
                        break
            else:
                parent_bone = edit_bones.get(expected_parent)
            
            if parent_bone and bone.parent != parent_bone:
                bone.parent = parent_bone
                reparented_count += 1
                logger.debug(f"Reparented {bone_name} to {parent_bone.name}")
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
    except Exception as e:
        logger.warning(f"Error fixing bone parenting: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
    
    if reparented_count > 0:
        logger.info(f"Reparented {reparented_count} bones for Unity compatibility")
    
    return reparented_count


def standardize_twist_bone_names(context: Context, armature: Object) -> int:
    """
    Standardize twist bone names to Unity-compatible format.
    
    Returns:
        Number of bones renamed
    """
    renamed_count = 0
    
    # MMD twist bone names -> Unity standard names
    twist_name_map = {
        # Japanese twist bones
        '左腕捩': 'UpperArmTwist_L',
        '右腕捩': 'UpperArmTwist_R',
        '左手捩': 'LowerArmTwist_L',
        '右手捩': 'LowerArmTwist_R',
        # Common variations
        'ArmTwist_L': 'UpperArmTwist_L',
        'ArmTwist_R': 'UpperArmTwist_R',
        'WristTwist_L': 'LowerArmTwist_L',
        'WristTwist_R': 'LowerArmTwist_R',
        'HandTwist_L': 'LowerArmTwist_L',
        'HandTwist_R': 'LowerArmTwist_R',
    }
    
    meshes = get_meshes_for_armature(armature)
    
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        edit_bones = armature.data.edit_bones
        
        for old_name, new_name in twist_name_map.items():
            if old_name in edit_bones and new_name not in edit_bones:
                edit_bones[old_name].name = new_name
                renamed_count += 1
                
                # Also update vertex groups
                bpy.ops.object.mode_set(mode='OBJECT')
                for mesh in meshes:
                    if old_name in mesh.vertex_groups:
                        mesh.vertex_groups[old_name].name = new_name
                bpy.ops.object.mode_set(mode='EDIT')
                
                logger.debug(f"Standardized twist bone: {old_name} -> {new_name}")
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
    except Exception as e:
        logger.warning(f"Error standardizing twist bone names: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
    
    return renamed_count


def remove_zero_weight_bones(context: Context, armature: Object,
                              protected_bones: Optional[Set[str]] = None) -> int:
    """
    Remove bones that have no vertex weights assigned.
    
    Args:
        context: Blender context
        armature: The armature object
        protected_bones: Set of bone names to never remove
        
    Returns:
        Number of bones removed
    """
    if protected_bones is None:
        protected_bones = {
            'Hips', 'Spine', 'Chest', 'UpperChest', 'Neck', 'Head',
            'Shoulder_L', 'Shoulder_R', 'UpperArm_L', 'UpperArm_R',
            'LowerArm_L', 'LowerArm_R', 'Hand_L', 'Hand_R',
            'UpperLeg_L', 'UpperLeg_R', 'LowerLeg_L', 'LowerLeg_R',
            'Foot_L', 'Foot_R', 'Toes_L', 'Toes_R',
            'Eye_L', 'Eye_R', 'LeftEye', 'RightEye',
        }
    
    meshes = get_meshes_for_armature(armature)
    removed_count = 0
    
    # Find bones with weights
    bones_with_weights: Set[str] = set()
    
    for mesh in meshes:
        for vg in mesh.vertex_groups:
            vg_index = vg.index
            for vert in mesh.data.vertices:
                for group in vert.groups:
                    if group.group == vg_index and group.weight > 0.0001:
                        bones_with_weights.add(vg.name)
                        break
    
    # Find bones to remove
    bones_to_remove: List[str] = []
    
    for bone in armature.data.bones:
        if bone.name not in bones_with_weights and bone.name not in protected_bones:
            # Don't remove bones that have children with weights
            has_weighted_children = False
            for child in bone.children_recursive:
                if child.name in bones_with_weights:
                    has_weighted_children = True
                    break
            
            if not has_weighted_children:
                bones_to_remove.append(bone.name)
    
    # Remove bones
    if bones_to_remove:
        try:
            set_active(armature)
            bpy.ops.object.mode_set(mode='EDIT')
            
            edit_bones = armature.data.edit_bones
            
            for bone_name in bones_to_remove:
                if bone_name in edit_bones:
                    bone = edit_bones[bone_name]
                    
                    # Reparent children first
                    parent = bone.parent
                    for child in list(bone.children):
                        child.parent = parent
                    
                    edit_bones.remove(bone)
                    removed_count += 1
                    logger.debug(f"Removed zero-weight bone: {bone_name}")
            
            bpy.ops.object.mode_set(mode='OBJECT')
            
        except Exception as e:
            logger.warning(f"Error removing zero-weight bones: {e}")
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except:
                pass
    
    if removed_count > 0:
        logger.info(f"Removed {removed_count} zero-weight bones")
    
    return removed_count


def connect_bones_to_children(context: Context, armature: Object,
                               min_distance: float = 0.001) -> int:
    """
    Connect bones to their children where appropriate.
    This creates cleaner bone chains.
    
    Args:
        context: Blender context
        armature: The armature object
        min_distance: Minimum distance to consider bones as connected
        
    Returns:
        Number of bones connected
    """
    connected_count = 0
    
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        edit_bones = armature.data.edit_bones
        
        for bone in edit_bones:
            # Skip bones with multiple children or no children
            if len(bone.children) != 1:
                continue
            
            child = bone.children[0]
            
            # Check if bone tail is close to child head
            distance = (bone.tail - child.head).length
            
            if distance < min_distance:
                # Connect child to parent
                child.use_connect = True
                connected_count += 1
                logger.debug(f"Connected {child.name} to {bone.name}")
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
    except Exception as e:
        logger.warning(f"Error connecting bones: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
    
    if connected_count > 0:
        logger.info(f"Connected {connected_count} bones to their parents")
    
    return connected_count


def fix_armature_name(armature: Object, new_name: str = "Armature") -> bool:
    """
    Rename armature to standard name.
    
    Args:
        armature: The armature object
        new_name: New name for the armature
        
    Returns:
        True if renamed, False otherwise
    """
    if armature.name == new_name:
        return False
    
    old_name = armature.name
    armature.name = new_name
    
    # Also rename armature data
    if armature.data.name != new_name:
        armature.data.name = new_name
    
    logger.info(f"Renamed armature: {old_name} -> {new_name}")
    return True
