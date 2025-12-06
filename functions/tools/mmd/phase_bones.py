# GPL License
# Avatar Toolkit MMD Converter - Bone Processing Functions (Phase 5, 6, 7)

import bpy
from typing import Dict, List
from bpy.types import Context, Object

from ....core.logging_setup import logger
from ....core.common import get_meshes_for_armature, set_active, has_shapekeys
from ....core.mmd.translations import translateFromJp, jp_half_to_full_tuples
from ....core.dictionaries import simplify_bonename, reverse_bone_lookup
from ....core.enhanced_dictionaries import unity_bone_names

from .phase_mesh import contains_japanese


# Prefixes and suffixes to remove from bone names
BONE_NAME_PREFIXES_TO_REMOVE: List[str] = [
    'Bip01_', 'Bip01 ', 'Bip001_', 'Bip001 ',
    'Character1_', 'Character1 ',
    'Def_', 'DEF_', 'DEF-', 'Def-',
    'ORG_', 'ORG-', 'Org_', 'Org-',
    'MCH_', 'MCH-', 'Mch_', 'Mch-',
    'JNT_', 'JNT-', 'Jnt_', 'Jnt-',
    'Bone_', 'BONE_', 'bone_',
    'mixamorig:', 'mixamorig_',
    'Armature|', 'Armature_',
    'CC_Base_', 'CC_Game_',
    'ValveBiped.', 'ValveBiped_',
    'HumanoidRoot/', 'HumanoidRoot_',
]

BONE_NAME_SUFFIXES_TO_REMOVE: List[str] = [
    '_end', '.end', '_End', '.End',
    '_tip', '.tip', '_Tip', '.Tip',
    '_nub', '.nub', '_Nub', '.Nub',
    '_null', '.null', '_Null', '.Null',
]


def get_unique_bone_name(armature: Object, base_name: str, current_name: str) -> str:
    """Get a unique bone name that doesn't conflict with existing bones."""
    if base_name == current_name:
        return base_name
    
    # Check if name already exists (excluding current bone)
    existing_names = {b.name for b in armature.data.edit_bones if b.name != current_name}
    
    if base_name not in existing_names:
        return base_name
    
    # Generate unique name with suffix
    counter = 1
    while f"{base_name}.{counter:03d}" in existing_names:
        counter += 1
    
    return f"{base_name}.{counter:03d}"


def translate_bone_names(armature: Object) -> int:
    """Translate bone names from Japanese to English.
    Also updates vertex groups in all meshes."""
    translated_count = 0
    bone_rename_map: Dict[str, str] = {}
    
    # First pass: collect renames (can't rename while iterating)
    for bone in armature.data.bones:
        original_name = bone.name
        if contains_japanese(original_name):
            # Convert half-width to full-width first
            new_name = original_name
            for half, full in jp_half_to_full_tuples:
                new_name = new_name.replace(half, full)
            
            # Then translate using dictionary
            new_name = translateFromJp(new_name)
            
            if new_name != original_name:
                bone_rename_map[original_name] = new_name
    
    if not bone_rename_map:
        return 0
    
    # Need to rename in edit mode
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        for old_name, new_name in bone_rename_map.items():
            if old_name in armature.data.edit_bones:
                # Ensure unique name
                final_name = get_unique_bone_name(armature, new_name, old_name)
                armature.data.edit_bones[old_name].name = final_name
                translated_count += 1
                logger.debug(f"Translated bone: {old_name} -> {final_name}")
                
                # Update the map with final name for vertex group renaming
                bone_rename_map[old_name] = final_name
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Update vertex groups in all meshes
        meshes = get_meshes_for_armature(armature)
        for mesh in meshes:
            for old_name, new_name in bone_rename_map.items():
                if old_name in mesh.vertex_groups:
                    mesh.vertex_groups[old_name].name = new_name
        
    except Exception as e:
        logger.error(f"Error translating bone names: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
    
    return translated_count


def translate_shapekey_names(armature: Object) -> int:
    """Translate shape key names from Japanese to English."""
    translated_count = 0
    meshes = get_meshes_for_armature(armature)
    
    for mesh in meshes:
        if not has_shapekeys(mesh):
            continue
        
        for key_block in mesh.data.shape_keys.key_blocks:
            # Skip basis
            if key_block.name == 'Basis':
                continue
            
            original_name = key_block.name
            if contains_japanese(original_name):
                new_name = original_name
                for half, full in jp_half_to_full_tuples:
                    new_name = new_name.replace(half, full)
                
                new_name = translateFromJp(new_name)
                
                if new_name != original_name:
                    key_block.name = new_name
                    translated_count += 1
                    logger.debug(f"Translated shape key: {original_name} -> {new_name}")
    
    return translated_count


def translate_object_names(armature: Object) -> int:
    """Translate object names (meshes, etc.) from Japanese to English."""
    translated_count = 0
    
    # Translate armature name
    if contains_japanese(armature.name):
        original_name = armature.name
        new_name = original_name
        for half, full in jp_half_to_full_tuples:
            new_name = new_name.replace(half, full)
        new_name = translateFromJp(new_name)
        
        if new_name != original_name:
            armature.name = new_name
            translated_count += 1
            logger.debug(f"Translated armature: {original_name} -> {new_name}")
    
    # Translate mesh names
    meshes = get_meshes_for_armature(armature)
    for mesh in meshes:
        if contains_japanese(mesh.name):
            original_name = mesh.name
            new_name = original_name
            for half, full in jp_half_to_full_tuples:
                new_name = new_name.replace(half, full)
            new_name = translateFromJp(new_name)
            
            if new_name != original_name:
                mesh.name = new_name
                translated_count += 1
                logger.debug(f"Translated mesh: {original_name} -> {new_name}")
    
    # Translate parent empty if exists
    if armature.parent and armature.parent.type == 'EMPTY':
        empty = armature.parent
        if contains_japanese(empty.name):
            original_name = empty.name
            new_name = original_name
            for half, full in jp_half_to_full_tuples:
                new_name = new_name.replace(half, full)
            new_name = translateFromJp(new_name)
            
            if new_name != original_name:
                empty.name = new_name
                translated_count += 1
                logger.debug(f"Translated parent empty: {original_name} -> {new_name}")
    
    return translated_count


def rename_bones_from_dictionary(context: Context, armature: Object, 
                                  rename_dict: Dict[str, List[str]]) -> int:
    """Rename bones using the rename dictionary (MMD -> Unity standard names).
    Also updates vertex groups in meshes."""
    renamed_count = 0
    bone_rename_map: Dict[str, str] = {}
    
    # Build a map of old_name -> new_name
    for new_name, old_names in rename_dict.items():
        for old_name in old_names:
            # Check both exact match and simplified match
            for bone in armature.data.bones:
                if bone.name == old_name or simplify_bonename(bone.name) == simplify_bonename(old_name):
                    if bone.name not in bone_rename_map:
                        bone_rename_map[bone.name] = new_name
                        break
    
    if not bone_rename_map:
        logger.debug("No bones to rename from dictionary")
        return 0
    
    # Rename bones in edit mode
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        for old_name, new_name in bone_rename_map.items():
            if old_name in armature.data.edit_bones:
                # Check if new_name already exists
                if new_name in armature.data.edit_bones and new_name != old_name:
                    logger.debug(f"Skipping rename {old_name} -> {new_name}: target exists")
                    continue
                
                armature.data.edit_bones[old_name].name = new_name
                renamed_count += 1
                logger.debug(f"Renamed bone: {old_name} -> {new_name}")
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Update vertex groups in all meshes
        meshes = get_meshes_for_armature(armature)
        for mesh in meshes:
            for old_name, new_name in bone_rename_map.items():
                if old_name in mesh.vertex_groups:
                    # Check if target already exists
                    if new_name in mesh.vertex_groups:
                        continue
                    mesh.vertex_groups[old_name].name = new_name
        
    except Exception as e:
        logger.error(f"Error renaming bones from dictionary: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
    
    return renamed_count


def unhide_all_bones(armature: Object) -> None:
    """Unhide all bones (both edit bones and pose bones).
    Makes all bones visible and selectable."""
    try:
        # Unhide in edit mode
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        for edit_bone in armature.data.edit_bones:
            edit_bone.hide = False
            edit_bone.hide_select = False
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Unhide pose bones
        for pose_bone in armature.pose.bones:
            bone = armature.data.bones.get(pose_bone.name)
            if bone:
                bone.hide = False
                bone.hide_select = False
        
        logger.debug(f"Unhid all {len(armature.data.bones)} bones")
        
    except Exception as e:
        logger.warning(f"Error unhiding bones: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass


def reset_pose_position(armature: Object) -> None:
    """Reset pose position - clear all bone rotations, scales, and transforms.
    Returns all bones to their rest pose."""
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='POSE')
        
        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.pose.transforms_clear()
        
        # Also manually reset each bone to be safe
        for pose_bone in armature.pose.bones:
            pose_bone.location = (0, 0, 0)
            pose_bone.rotation_quaternion = (1, 0, 0, 0)
            pose_bone.rotation_euler = (0, 0, 0)
            pose_bone.rotation_axis_angle = (0, 0, 1, 0)
            pose_bone.scale = (1, 1, 1)
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
        logger.debug("Reset pose position for all bones")
        
    except Exception as e:
        logger.warning(f"Error resetting pose position: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass


def remove_all_bone_collections(armature: Object) -> int:
    """Remove all bone collections from the armature."""
    removed = 0
    
    # Get all collection names first to avoid modification during iteration
    collection_names = [c.name for c in armature.data.collections]
    
    for name in collection_names:
        if name in armature.data.collections:
            try:
                armature.data.collections.remove(armature.data.collections[name])
                removed += 1
            except Exception as e:
                logger.debug(f"Could not remove bone collection {name}: {e}")
    
    return removed


def delete_all_bone_constraints(armature: Object) -> int:
    """Delete all bone constraints from pose bones.
    This removes IK, Copy Rotation, Damped Track, etc."""
    removed_count = 0
    
    for pose_bone in armature.pose.bones:
        # Get list of constraint names first
        constraint_names = [c.name for c in pose_bone.constraints]
        
        for constraint_name in constraint_names:
            try:
                constraint = pose_bone.constraints.get(constraint_name)
                if constraint:
                    pose_bone.constraints.remove(constraint)
                    removed_count += 1
            except Exception as e:
                logger.debug(f"Could not remove constraint {constraint_name} from {pose_bone.name}: {e}")
    
    return removed_count


def reset_bone_visibility(armature: Object) -> None:
    """Reset bone visibility and layers for all bones.
    Ensures all bones are visible and on default layer."""
    try:
        # Reset bone visibility in armature data
        for bone in armature.data.bones:
            bone.hide = False
            bone.hide_select = False
        
        # Reset pose bone custom shapes and visibility
        for pose_bone in armature.pose.bones:
            # Clear custom bone shapes
            pose_bone.custom_shape = None
            pose_bone.custom_shape_scale_xyz = (1, 1, 1)
            
            # Reset bone group (color)
            pose_bone.bone_group = None
        
        # Ensure armature display settings are visible
        armature.data.display_type = 'OCTAHEDRAL'
        armature.show_in_front = False
        
        logger.debug("Reset bone visibility for all bones")
        
    except Exception as e:
        logger.warning(f"Error resetting bone visibility: {e}")


def clean_bone_name_prefixes(context: Context, armature: Object) -> int:
    """Clean up bone names by removing common prefixes and suffixes.
    Also replaces spaces, dashes, and dots with underscores."""
    cleaned_count = 0
    rename_map: Dict[str, str] = {}
    
    for bone in armature.data.bones:
        original_name = bone.name
        new_name = original_name
        
        # Remove prefixes
        for prefix in BONE_NAME_PREFIXES_TO_REMOVE:
            if new_name.startswith(prefix):
                new_name = new_name[len(prefix):]
                break
        
        # Remove suffixes
        for suffix in BONE_NAME_SUFFIXES_TO_REMOVE:
            if new_name.endswith(suffix):
                new_name = new_name[:-len(suffix)]
                break
        
        # Replace problematic characters with underscores
        new_name = new_name.replace(' ', '_')
        new_name = new_name.replace('-', '_')
        
        # Don't replace dots in side indicators like .L or .R
        if not (new_name.endswith('.L') or new_name.endswith('.R') or 
                new_name.endswith('.l') or new_name.endswith('.r')):
            # Replace dots except for common patterns
            parts = new_name.rsplit('.', 1)
            if len(parts) == 2 and parts[1].isdigit():
                # Keep .001, .002 etc
                pass
            elif len(parts) == 2 and parts[1].lower() in ['l', 'r', 'left', 'right']:
                # Keep side indicators
                pass
            else:
                new_name = new_name.replace('.', '_')
        
        if new_name != original_name:
            rename_map[original_name] = new_name
    
    # Apply renames in edit mode
    if rename_map:
        cleaned_count = apply_bone_renames(context, armature, rename_map)
    
    return cleaned_count


def standardize_side_indicators(context: Context, armature: Object) -> int:
    """
    Standardize bone side indicators:
    - LEFT, Left -> _L or .L
    - RIGHT, Right -> _R or .R
    - _Le_, _le_ -> _L_
    - _Ri_, _ri_ -> _R_
    """
    standardized_count = 0
    rename_map: Dict[str, str] = {}
    
    # Patterns to standardize (old -> new)
    side_patterns = [
        # Full word replacements at end
        ('_LEFT', '_L'), ('_Left', '_L'), ('_left', '_L'),
        ('_RIGHT', '_R'), ('_Right', '_R'), ('_right', '_R'),
        ('.LEFT', '.L'), ('.Left', '.L'), ('.left', '.L'),
        ('.RIGHT', '.R'), ('.Right', '.R'), ('.right', '.R'),
        # Abbreviated patterns
        ('_Le_', '_L_'), ('_le_', '_L_'), ('_LE_', '_L_'),
        ('_Ri_', '_R_'), ('_ri_', '_R_'), ('_RI_', '_R_'),
        # Prefix patterns
        ('Left_', 'L_'), ('LEFT_', 'L_'), ('left_', 'L_'),
        ('Right_', 'R_'), ('RIGHT_', 'R_'), ('right_', 'R_'),
        # Handle full words at start
        ('Left', 'L'), ('RIGHT', 'R'),
    ]
    
    for bone in armature.data.bones:
        original_name = bone.name
        new_name = original_name
        
        # Apply side pattern replacements
        for old_pattern, new_pattern in side_patterns:
            if old_pattern in new_name:
                new_name = new_name.replace(old_pattern, new_pattern)
                break
        
        if new_name != original_name:
            rename_map[original_name] = new_name
    
    # Apply renames
    if rename_map:
        standardized_count = apply_bone_renames(context, armature, rename_map)
    
    return standardized_count


def rename_bones_with_dictionary(context: Context, armature: Object) -> int:
    """
    Rename bones using the comprehensive bone dictionary to Unity standard names.
    Uses reverse_bone_lookup from dictionaries.py to find matches,
    then converts to Unity Humanoid standard naming using unity_bone_names.
    """
    renamed_count = 0
    rename_map: Dict[str, str] = {}
    
    for bone in armature.data.bones:
        original_name = bone.name
        simplified = simplify_bonename(original_name)
        
        # Look up in reverse bone dictionary
        if simplified in reverse_bone_lookup:
            dict_name = reverse_bone_lookup[simplified]
            
            # Convert to Unity standard name if we have a mapping
            if dict_name in unity_bone_names:
                unity_name = unity_bone_names[dict_name]
                if unity_name != original_name:
                    rename_map[original_name] = unity_name
            elif dict_name != original_name:
                # If no Unity mapping, still use the dictionary name (for non-standard bones)
                rename_map[original_name] = dict_name
    
    # Apply renames
    if rename_map:
        renamed_count = apply_bone_renames(context, armature, rename_map)
    
    return renamed_count


def resolve_conflicting_bone_names(context: Context, armature: Object) -> int:
    """
    Resolve conflicting bone names (e.g., multiple bones named "Spine").
    Appends numbers to make names unique while preserving hierarchy hints.
    """
    resolved_count = 0
    
    # Find duplicate names
    name_counts: Dict[str, int] = {}
    for bone in armature.data.bones:
        name = bone.name
        name_counts[name] = name_counts.get(name, 0) + 1
    
    # Process bones with duplicate names
    name_counters: Dict[str, int] = {}
    
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        for edit_bone in armature.data.edit_bones:
            name = edit_bone.name
            
            if name_counts.get(name, 0) > 1:
                # This name has duplicates
                counter = name_counters.get(name, 1)
                name_counters[name] = counter + 1
                
                # Try to use hierarchy position for naming
                if edit_bone.parent:
                    parent_suffix = f"_{counter}"
                else:
                    parent_suffix = f"_{counter}"
                
                new_name = f"{name}{parent_suffix}"
                
                # Make sure new name is unique
                while new_name in armature.data.edit_bones:
                    counter += 1
                    new_name = f"{name}_{counter}"
                
                edit_bone.name = new_name
                resolved_count += 1
                logger.debug(f"Resolved conflict: {name} -> {new_name}")
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
    except Exception as e:
        logger.warning(f"Error resolving conflicting bone names: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
    
    return resolved_count


def apply_bone_renames(context: Context, armature: Object, 
                       rename_map: Dict[str, str]) -> int:
    """
    Apply bone renames and update vertex groups in meshes.
    
    Args:
        context: Blender context
        armature: The armature object
        rename_map: Dictionary mapping old names to new names
        
    Returns:
        Number of bones renamed
    """
    renamed_count = 0
    
    if not rename_map:
        return 0
    
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        for old_name, new_name in rename_map.items():
            if old_name in armature.data.edit_bones:
                # Check if new name already exists
                if new_name in armature.data.edit_bones and new_name != old_name:
                    logger.debug(f"Skipping rename {old_name} -> {new_name}: target exists")
                    continue
                
                armature.data.edit_bones[old_name].name = new_name
                renamed_count += 1
                logger.debug(f"Renamed bone: {old_name} -> {new_name}")
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Update vertex groups in all meshes
        meshes = get_meshes_for_armature(armature)
        for mesh in meshes:
            for old_name, new_name in rename_map.items():
                if old_name in mesh.vertex_groups:
                    if new_name not in mesh.vertex_groups:
                        mesh.vertex_groups[old_name].name = new_name
        
    except Exception as e:
        logger.error(f"Error applying bone renames: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
    
    return renamed_count
