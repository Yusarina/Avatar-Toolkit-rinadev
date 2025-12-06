# GPL License
# Avatar Toolkit MMD Converter - Weight Merging (Phase 11)

import bpy
from typing import Dict, List, Set
from bpy.types import Context, Object

from ....core.logging_setup import logger
from ....core.common import (
    get_meshes_for_armature,
    set_active,
    transfer_vertex_weights,
    get_vertex_weights,
)


def process_reweight_dictionary(context: Context, armature: Object,
                                 reweight_dict: Dict[str, List[str]],
                                 threshold: float = 0.01) -> int:
    """
    Process the reweight dictionary to merge vertex weights from old bones to new bones.
    
    Args:
        context: Blender context
        armature: The armature object
        reweight_dict: Dictionary mapping new bone names to lists of old bone names
        threshold: Minimum weight to transfer
        
    Returns:
        Number of weight transfers performed
    """
    meshes = get_meshes_for_armature(armature)
    transfer_count = 0
    
    if not meshes:
        logger.warning("No meshes found for weight merging")
        return 0
    
    for mesh in meshes:
        for target_bone, source_bones in reweight_dict.items():
            for source_bone in source_bones:
                # Skip if source doesn't exist or is same as target
                if source_bone == target_bone:
                    continue
                    
                if source_bone not in mesh.vertex_groups:
                    continue
                
                # Transfer weights
                try:
                    transfer_vertex_weights(mesh, source_bone, target_bone, threshold)
                    transfer_count += 1
                    logger.debug(f"Transferred weights: {source_bone} -> {target_bone} in {mesh.name}")
                except Exception as e:
                    logger.debug(f"Could not transfer weights {source_bone} -> {target_bone}: {e}")
    
    if transfer_count > 0:
        logger.info(f"Transferred {transfer_count} vertex group weights")
    
    return transfer_count


def merge_finger_weights(context: Context, armature: Object, 
                         threshold: float = 0.01) -> int:
    """
    Merge finger bone weights - consolidate multiple finger segments if needed.
    
    Returns:
        Number of weight merges performed
    """
    meshes = get_meshes_for_armature(armature)
    merge_count = 0
    
    # Finger patterns: some models have extra finger bones that should be merged
    # e.g., "Thumb0_L" should go to "Thumb1_L" if Thumb0 isn't a standard bone
    finger_merge_patterns = {
        # Non-standard finger bones -> standard finger bones
        'Thumb0_L': 'Thumb1_L',
        'Thumb0_R': 'Thumb1_R',
        'Index0_L': 'Index1_L',
        'Index0_R': 'Index1_R',
        'Middle0_L': 'Middle1_L',
        'Middle0_R': 'Middle1_R',
        'Ring0_L': 'Ring1_L',
        'Ring0_R': 'Ring1_R',
        'Little0_L': 'Little1_L',
        'Little0_R': 'Little1_R',
        'Pinky0_L': 'Little1_L',
        'Pinky0_R': 'Little1_R',
    }
    
    for mesh in meshes:
        for source, target in finger_merge_patterns.items():
            if source in mesh.vertex_groups and target in mesh.vertex_groups:
                try:
                    transfer_vertex_weights(mesh, source, target, threshold)
                    merge_count += 1
                    logger.debug(f"Merged finger weights: {source} -> {target}")
                except Exception as e:
                    logger.debug(f"Could not merge finger weights: {e}")
    
    return merge_count


def handle_twist_bone_weights(context: Context, armature: Object,
                               merge_twist: bool = True,
                               threshold: float = 0.01) -> int:
    """
    Handle twist bone weights - either merge into parent or distribute properly.
    
    Args:
        context: Blender context
        armature: The armature object
        merge_twist: If True, merge twist weights into parent. If False, keep separate.
        threshold: Minimum weight threshold
        
    Returns:
        Number of twist bone weight operations
    """
    if not merge_twist:
        return 0
    
    meshes = get_meshes_for_armature(armature)
    handled_count = 0
    
    # Twist bone patterns and their target bones
    twist_to_parent = {
        # Upper arm twist -> Upper arm
        'UpperArmTwist_L': 'UpperArm_L',
        'UpperArmTwist_R': 'UpperArm_R',
        'ArmTwist_L': 'UpperArm_L',
        'ArmTwist_R': 'UpperArm_R',
        'Arm_twist_L': 'UpperArm_L',
        'Arm_twist_R': 'UpperArm_R',
        # Lower arm twist -> Lower arm
        'LowerArmTwist_L': 'LowerArm_L',
        'LowerArmTwist_R': 'LowerArm_R',
        'HandTwist_L': 'LowerArm_L',
        'HandTwist_R': 'LowerArm_R',
        'Wrist_twist_L': 'LowerArm_L',
        'Wrist_twist_R': 'LowerArm_R',
        # Upper leg twist -> Upper leg
        'UpperLegTwist_L': 'UpperLeg_L',
        'UpperLegTwist_R': 'UpperLeg_R',
        'LegTwist_L': 'UpperLeg_L',
        'LegTwist_R': 'UpperLeg_R',
        # Lower leg twist -> Lower leg
        'LowerLegTwist_L': 'LowerLeg_L',
        'LowerLegTwist_R': 'LowerLeg_R',
    }
    
    for mesh in meshes:
        for twist_bone, parent_bone in twist_to_parent.items():
            if twist_bone in mesh.vertex_groups:
                # Check if parent exists, if not try alternative names
                target = parent_bone
                if target not in mesh.vertex_groups:
                    # Try without underscore
                    alt_target = parent_bone.replace('_L', '.L').replace('_R', '.R')
                    if alt_target in mesh.vertex_groups:
                        target = alt_target
                    else:
                        # Create the target group
                        mesh.vertex_groups.new(name=target)
                
                try:
                    transfer_vertex_weights(mesh, twist_bone, target, threshold)
                    handled_count += 1
                    logger.debug(f"Merged twist bone weights: {twist_bone} -> {target}")
                except Exception as e:
                    logger.debug(f"Could not merge twist weights: {e}")
    
    return handled_count


def cleanup_unused_vertex_groups(context: Context, armature: Object) -> int:
    """
    Remove vertex groups that have no weights or don't correspond to bones.
    
    Returns:
        Number of vertex groups removed
    """
    meshes = get_meshes_for_armature(armature)
    removed_count = 0
    
    # Get list of bone names
    bone_names = {bone.name for bone in armature.data.bones}
    
    for mesh in meshes:
        groups_to_remove: List[str] = []
        
        for vg in mesh.vertex_groups:
            # Check if vertex group has any weights
            has_weights = False
            vg_index = vg.index
            
            for vert in mesh.data.vertices:
                for group in vert.groups:
                    if group.group == vg_index and group.weight > 0.0001:
                        has_weights = True
                        break
                if has_weights:
                    break
            
            # If no weights, mark for removal
            if not has_weights:
                groups_to_remove.append(vg.name)
        
        # Remove marked groups
        for group_name in groups_to_remove:
            try:
                vg = mesh.vertex_groups.get(group_name)
                if vg:
                    mesh.vertex_groups.remove(vg)
                    removed_count += 1
                    logger.debug(f"Removed empty vertex group: {group_name}")
            except Exception as e:
                logger.debug(f"Could not remove vertex group {group_name}: {e}")
    
    if removed_count > 0:
        logger.info(f"Removed {removed_count} empty vertex groups")
    
    return removed_count
