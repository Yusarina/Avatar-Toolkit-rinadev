# GPL License
# Avatar Toolkit MMD Converter - Hierarchy Processing Functions (Phase 8)

import bpy
from typing import List
from bpy.types import Context, Object

from ....core.logging_setup import logger
from ....core.common import get_meshes_for_armature, set_active
from ....core.dictionaries import simplify_bonename, reverse_bone_lookup


# Bones that should be removed (twist/helper bones)
TWIST_BONE_PATTERNS: List[str] = [
    'twist', 'Twist', 'TWIST',
    '捩', '捩り',  # Japanese for twist
    'roll', 'Roll', 'ROLL',
    'helper', 'Helper', 'HELPER',
    'adjust', 'Adjust', 'ADJUST',
    'cancel', 'Cancel', 'CANCEL',
    'キャンセル',  # Japanese for cancel
    'IK親', 'IK_親',  # IK parent
    'ダミー', 'Dummy',  # Dummy
]

# Bones that are considered "end" bones
END_BONE_PATTERNS: List[str] = [
    '_end', '.end', '_End', '.End',
    '_tip', '.tip', '_Tip', '.Tip',
    '_nub', '.nub', '_Nub', '.Nub',
    '先', '先端',  # Japanese for tip/end
]

# Bones that should be merged into Hips (parent nodes)
HIPS_PARENT_BONES: List[str] = [
    'ParentNode', 'parentnode', 'PARENTNODE',
    'Root', 'root', 'ROOT',
    '全ての親',  # Japanese: "Parent of all"
    'Center', 'center', 'CENTER',
    'センター',  # Japanese: Center
    'MasterRoot', 'masterroot',
    'Armature', 'armature',
    'ControlNode', 'controlnode',
    '操作中心',  # Japanese: Control center
]


def merge_vertex_group_weights(mesh: Object, source_group: str, target_group: str) -> None:
    """
    Merge vertex weights from source group to target group.
    """
    if source_group not in mesh.vertex_groups:
        return
    
    source_vg = mesh.vertex_groups[source_group]
    
    # Create target group if it doesn't exist
    if target_group not in mesh.vertex_groups:
        target_vg = mesh.vertex_groups.new(name=target_group)
    else:
        target_vg = mesh.vertex_groups[target_group]
    
    # Get source group index
    source_index = source_vg.index
    
    # Transfer weights
    for vert in mesh.data.vertices:
        for group in vert.groups:
            if group.group == source_index:
                # Add weight to target group
                try:
                    target_vg.add([vert.index], group.weight, 'ADD')
                except:
                    pass
    
    # Remove source group
    mesh.vertex_groups.remove(source_vg)
    logger.debug(f"Merged vertex group {source_group} into {target_group}")


def remove_twist_bones(context: Context, armature: Object) -> int:
    """
    Remove twist/helper bones and transfer weights to parent bones.
    """
    removed_count = 0
    bones_to_remove: List[str] = []
    
    # Find twist bones
    for bone in armature.data.bones:
        for pattern in TWIST_BONE_PATTERNS:
            if pattern in bone.name:
                bones_to_remove.append(bone.name)
                break
    
    if not bones_to_remove:
        return 0
    
    # Get meshes for weight transfer
    meshes = get_meshes_for_armature(armature)
    
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        for bone_name in bones_to_remove:
            if bone_name in armature.data.edit_bones:
                edit_bone = armature.data.edit_bones[bone_name]
                parent_name = edit_bone.parent.name if edit_bone.parent else None
                
                # Reparent children to this bone's parent
                for child in list(edit_bone.children):
                    child.parent = edit_bone.parent
                
                # Remove the bone
                armature.data.edit_bones.remove(edit_bone)
                removed_count += 1
                
                # Transfer weights to parent
                if parent_name:
                    for mesh in meshes:
                        merge_vertex_group_weights(mesh, bone_name, parent_name)
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
    except Exception as e:
        logger.warning(f"Error removing twist bones: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
    
    return removed_count


def remove_end_bones(context: Context, armature: Object) -> int:
    """
    Remove end/tip bones that don't have any children or weights.
    """
    removed_count = 0
    bones_to_remove: List[str] = []
    
    # Find end bones
    for bone in armature.data.bones:
        is_end_bone = False
        
        # Check patterns
        for pattern in END_BONE_PATTERNS:
            if pattern in bone.name:
                is_end_bone = True
                break
        
        # Also consider bones without children as potential end bones
        if not is_end_bone and len(bone.children) == 0:
            # Only if it matches naming patterns
            for pattern in END_BONE_PATTERNS:
                if bone.name.lower().endswith(pattern.lower()):
                    is_end_bone = True
                    break
        
        if is_end_bone:
            bones_to_remove.append(bone.name)
    
    if not bones_to_remove:
        return 0
    
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        for bone_name in bones_to_remove:
            if bone_name in armature.data.edit_bones:
                edit_bone = armature.data.edit_bones[bone_name]
                
                # Only remove if it has no children
                if len(edit_bone.children) == 0:
                    armature.data.edit_bones.remove(edit_bone)
                    removed_count += 1
                    logger.debug(f"Removed end bone: {bone_name}")
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
    except Exception as e:
        logger.warning(f"Error removing end bones: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
    
    return removed_count


def disconnect_bones_and_reset_roll(context: Context, armature: Object) -> None:
    """
    Disconnect all bones (use_connect = False) and reset roll to 0.
    This allows for cleaner hierarchy manipulation.
    """
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        for edit_bone in armature.data.edit_bones:
            # Disconnect from parent
            edit_bone.use_connect = False
            
            # Reset roll to 0
            edit_bone.roll = 0.0
        
        bpy.ops.object.mode_set(mode='OBJECT')
        logger.debug("Disconnected all bones and reset roll to 0")
        
    except Exception as e:
        logger.warning(f"Error disconnecting bones: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass


def fix_bone_hierarchy(context: Context, armature: Object) -> None:
    """
    Fix bone hierarchy:
    1. Find or identify Hips bone
    2. Merge ParentNode/Root weights into Hips
    3. Make Hips the top-level parent
    4. Reparent orphan bones appropriately
    """
    meshes = get_meshes_for_armature(armature)
    
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        edit_bones = armature.data.edit_bones
        
        # Find or identify Hips bone
        hips_bone = None
        hips_candidates = ['Hips', 'hips', 'HIPS', 'Hip', 'hip', 'Pelvis', 'pelvis']
        
        for name in hips_candidates:
            if name in edit_bones:
                hips_bone = edit_bones[name]
                break
        
        # If no Hips found, try to find by hierarchy using simplified name matching
        if not hips_bone:
            for edit_bone in edit_bones:
                try:
                    simplified = simplify_bonename(edit_bone.name)
                    if simplified in reverse_bone_lookup:
                        if reverse_bone_lookup[simplified] == 'hips':
                            hips_bone = edit_bone
                            break
                except Exception:
                    # Skip bones with encoding issues
                    continue
        
        if not hips_bone:
            logger.warning("Could not find Hips bone - hierarchy fix skipped")
            bpy.ops.object.mode_set(mode='OBJECT')
            return
        
        # Find parent bones to merge into Hips (use exact name matching for safety)
        parent_bones_to_merge: List[str] = []
        safe_parent_patterns = ['ParentNode', 'parentnode', 'Root', 'root', 
                               'Center', 'center', 'MasterRoot', 'Armature']
        
        for pattern in safe_parent_patterns:
            if pattern in edit_bones and pattern != hips_bone.name:
                parent_bones_to_merge.append(pattern)
        
        # Also check if Hips has a parent that should be merged
        if hips_bone.parent:
            parent_name = hips_bone.parent.name
            try:
                # Safely get lowercase, handling encoding issues
                try:
                    parent_name_lower = parent_name.lower()
                except (UnicodeDecodeError, UnicodeEncodeError):
                    parent_name_lower = parent_name
                
                for pattern in safe_parent_patterns:
                    if pattern.lower() in parent_name_lower:
                        if parent_name not in parent_bones_to_merge:
                            parent_bones_to_merge.append(parent_name)
                        break
            except Exception:
                # If encoding fails, just add the parent anyway
                if parent_name not in parent_bones_to_merge:
                    parent_bones_to_merge.append(parent_name)
        
        # Merge parent bones into Hips
        for parent_name in parent_bones_to_merge:
            if parent_name in edit_bones:
                parent_bone = edit_bones[parent_name]
                
                # Reparent children of the parent bone to Hips (except Hips itself)
                for child in list(parent_bone.children):
                    if child != hips_bone:
                        child.parent = hips_bone
                
                bpy.ops.object.mode_set(mode='OBJECT')
                
                # Merge weights
                for mesh in meshes:
                    merge_vertex_group_weights(mesh, parent_name, hips_bone.name)
                
                bpy.ops.object.mode_set(mode='EDIT')
                
                # Remove the parent bone
                if parent_name in armature.data.edit_bones:
                    armature.data.edit_bones.remove(armature.data.edit_bones[parent_name])
                    logger.info(f"Merged {parent_name} into {hips_bone.name}")
        
        # Make Hips the root (no parent)
        # Need to refresh reference after potential removes
        if hips_bone.name in edit_bones:
            hips_bone = edit_bones[hips_bone.name]
            hips_bone.parent = None
        
        # Find orphan top-level bones and reparent appropriately
        # Spine, Legs should be children of Hips
        spine_patterns = ['Spine', 'spine', 'UpperBody', 'Torso']
        leg_patterns = ['Leg', 'leg', 'Thigh', 'UpperLeg', 'LeftUpperLeg', 'RightUpperLeg']
        
        for edit_bone in list(edit_bones):
            if edit_bone.parent is None and edit_bone != hips_bone:
                try:
                    # Safely get lowercase name, handling encoding issues
                    try:
                        bone_name_lower = edit_bone.name.lower()
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        # Skip bones with encoding issues
                        continue
                    
                    # Check if this should be a child of Hips
                    should_parent_to_hips = False
                    
                    for pattern in spine_patterns:
                        if pattern.lower() in bone_name_lower:
                            should_parent_to_hips = True
                            break
                    
                    if not should_parent_to_hips:
                        for pattern in leg_patterns:
                            if pattern.lower() in bone_name_lower:
                                should_parent_to_hips = True
                                break
                    
                    if should_parent_to_hips and hips_bone.name in edit_bones:
                        edit_bone.parent = edit_bones[hips_bone.name]
                        logger.debug(f"Reparented {edit_bone.name} to Hips")
                except Exception as e:
                    # Skip bones with encoding issues in name
                    logger.debug(f"Skipping bone due to error: {e}")
                    continue
        
        bpy.ops.object.mode_set(mode='OBJECT')
        logger.info("Fixed bone hierarchy - Hips is now top parent")
        
    except Exception as e:
        logger.error(f"Error fixing bone hierarchy: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
