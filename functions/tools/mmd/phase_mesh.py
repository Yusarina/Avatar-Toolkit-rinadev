# GPL License
# Avatar Toolkit MMD Converter - Mesh Processing Functions (Phase 4)

import bpy
from typing import List
from bpy.types import Context, Object

from ....core.logging_setup import logger
from ....core.common import (
    get_meshes_for_armature,
    set_active,
    has_shapekeys,
    clean_shapekeys,
    add_armature_modifier,
)
from ....core.mmd.translations import translateFromJp, jp_half_to_full_tuples


def remove_duplicate_armature_modifiers(mesh: Object, armature: Object) -> int:
    """Remove duplicate armature modifiers from a mesh.
    Keeps the first valid armature modifier pointing to our armature."""
    removed_count = 0
    found_valid = False
    
    to_remove: List[str] = []
    
    for mod in mesh.modifiers:
        if mod.type == 'ARMATURE':
            if mod.object == armature and not found_valid:
                found_valid = True
            else:
                to_remove.append(mod.name)
    
    # Remove duplicates
    for mod_name in to_remove:
        try:
            mesh.modifiers.remove(mesh.modifiers[mod_name])
            removed_count += 1
        except Exception as e:
            logger.warning(f"Could not remove duplicate modifier {mod_name}: {e}")
    
    if removed_count > 0:
        logger.debug(f"Removed {removed_count} duplicate armature modifiers from {mesh.name}")
    
    return removed_count


def ensure_armature_modifier(mesh: Object, armature: Object) -> bool:
    """Ensure mesh has an armature modifier pointing to the armature."""
    for mod in mesh.modifiers:
        if mod.type == 'ARMATURE' and mod.object == armature:
            return False
    
    # Add armature modifier
    try:
        add_armature_modifier(mesh, armature)
        logger.debug(f"Added armature modifier to {mesh.name}")
        return True
    except Exception as e:
        logger.warning(f"Could not add armature modifier to {mesh.name}: {e}")
        return False


def clean_mesh_shapekeys(mesh: Object) -> int:
    """Clean unused shape keys from a mesh."""
    if not has_shapekeys(mesh):
        return 0
    
    initial_count = len(mesh.data.shape_keys.key_blocks)
    
    try:
        clean_shapekeys(mesh)
        final_count = len(mesh.data.shape_keys.key_blocks) if mesh.data.shape_keys else 0
        removed = initial_count - final_count
        
        if removed > 0:
            logger.debug(f"Cleaned {removed} unused shape keys from {mesh.name}")
        
        return removed
    except Exception as e:
        logger.warning(f"Could not clean shape keys for {mesh.name}: {e}")
        return 0


def ensure_mesh_parenting(mesh: Object, armature: Object) -> None:
    """Ensure mesh is properly parented to the armature."""
    if mesh.parent != armature:
        matrix_world = mesh.matrix_world.copy()
        
        # Set parent
        mesh.parent = armature
        mesh.parent_type = 'OBJECT'
        
        # Restore world position
        mesh.matrix_world = matrix_world
        
        logger.debug(f"Re-parented {mesh.name} to {armature.name}")


def contains_japanese(text: str) -> bool:
    """Check if text contains Japanese characters"""
    for char in text:
        # Hiragana, Katakana, CJK Unified Ideographs
        if ('\u3040' <= char <= '\u309F' or  # Hiragana
            '\u30A0' <= char <= '\u30FF' or  # Katakana
            '\u4E00' <= char <= '\u9FFF' or  # CJK
            '\uFF00' <= char <= '\uFFEF'):   # Full-width
            return True
    return False


def translate_material_name(name: str) -> str:
    """Translate material name from Japanese to English"""
    # First convert half-width to full-width
    for half, full in jp_half_to_full_tuples:
        name = name.replace(half, full)
    
    # Then translate using dictionary
    translated = translateFromJp(name)
    
    # Clean up the name
    translated = translated.strip()
    translated = translated.replace(' ', '_')
    
    return translated if translated else name


def get_unique_material_name(base_name: str) -> str:
    """Get a unique material name"""
    if base_name not in bpy.data.materials:
        return base_name
    
    counter = 1
    while f"{base_name}.{counter:03d}" in bpy.data.materials:
        counter += 1
    
    return f"{base_name}.{counter:03d}"


def fix_material_names(mesh: Object) -> int:
    """Fix/translate material names from Japanese to English."""
    renamed_count = 0
    
    if not mesh.data.materials:
        return 0
    
    for mat_slot in mesh.material_slots:
        if not mat_slot.material:
            continue
        
        mat = mat_slot.material
        original_name = mat.name
        
        # Check if name contains Japanese characters
        if contains_japanese(original_name):
            new_name = translate_material_name(original_name)
            
            if new_name != original_name:
                # Ensure unique name
                new_name = get_unique_material_name(new_name)
                mat.name = new_name
                renamed_count += 1
                logger.debug(f"Renamed material: {original_name} -> {new_name}")
    
    if renamed_count > 0:
        logger.info(f"Renamed {renamed_count} materials in {mesh.name}")
    
    return renamed_count


def join_child_meshes(context: Context, armature: Object) -> None:
    """Join child meshes to a single mesh if multiple children exist.
    Uses ATK JoinAllMeshes operator."""
    meshes = get_meshes_for_armature(armature)
    
    if len(meshes) <= 1:
        logger.debug("Only one or no meshes found, skipping join")
        return
    
    logger.info(f"Joining {len(meshes)} meshes using ATK operator")
    
    try:
        # Ensure armature is active for the operator
        set_active(armature)
        
        result = bpy.ops.avatar_toolkit.join_all_meshes()
        
        if result == {'FINISHED'}:
            # Get the joined mesh and rename it
            meshes = get_meshes_for_armature(armature)
            if meshes:
                meshes[0].name = "Body"
                logger.info(f"Joined meshes into: {meshes[0].name}")
        else:
            logger.warning("ATK join meshes operator did not finish successfully")
            
    except Exception as e:
        logger.error(f"Error joining meshes: {e}")
