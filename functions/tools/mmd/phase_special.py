# GPL License
# Avatar Toolkit MMD Converter - Special Bone Fixes (Phase 9)

import bpy
from typing import List, Tuple, Any
from bpy.types import Context, Object
from mathutils import Vector

from ....core.logging_setup import logger
from ....core.common import get_meshes_for_armature, set_active

from .phase_hierarchy import merge_vertex_group_weights


# Spine bone name patterns for detection
SPINE_BONE_PATTERNS: List[str] = [
    'Spine', 'spine', 'SPINE',
    '脊椎', '上半身', '上半身2', '上半身3',
    'Torso', 'torso',
]

CHEST_BONE_PATTERNS: List[str] = [
    'Chest', 'chest', 'CHEST',
    '胸', '上胸',
    'UpperBody', 'upperbody',
]

UPPER_CHEST_PATTERNS: List[str] = [
    'UpperChest', 'upperchest', 'Upper_Chest', 'upper_chest',
    'Chest2', 'chest2',
    '上胸', '上半身3',
]

NECK_BONE_PATTERNS: List[str] = [
    'Neck', 'neck', 'NECK',
    '首', 'くび',
]

HEAD_BONE_PATTERNS: List[str] = [
    'Head', 'head', 'HEAD',
    '頭', 'あたま',
]


def fix_spine_hierarchy(context: Context, armature: Object, 
                        keep_upper_chest: bool = True) -> int:
    """
    Fix spine hierarchy for Unity/VRChat compatibility.
    
    Spine configurations:
    - 1 spine: Rename to Chest (or create Spine and make it Chest)
    - 2 spines: First is Spine, second is Chest
    - 3 spines: Spine, Chest, Upper Chest
    - 4+ spines: Merge extras into proper structure
    
    Returns: Number of bones modified
    """
    meshes = get_meshes_for_armature(armature)
    modified_count = 0
    
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        edit_bones = armature.data.edit_bones
        
        # Find all spine-related bones
        spine_bones: List[Tuple[str, Any]] = []  # (name, edit_bone)
        
        # First, look for bones already named Spine, Chest, UpperChest
        standard_spine = None
        standard_chest = None
        standard_upper_chest = None
        
        for bone_name in ['Spine', 'spine']:
            if bone_name in edit_bones:
                standard_spine = edit_bones[bone_name]
                break
        
        for bone_name in ['Chest', 'chest']:
            if bone_name in edit_bones:
                standard_chest = edit_bones[bone_name]
                break
        
        for bone_name in ['UpperChest', 'Upper_Chest', 'upperchest', 'upper_chest']:
            if bone_name in edit_bones:
                standard_upper_chest = edit_bones[bone_name]
                break
        
        # If we already have standard naming, check if hierarchy is correct
        if standard_spine and standard_chest:
            # Ensure proper parenting
            if standard_chest.parent != standard_spine:
                standard_chest.parent = standard_spine
                modified_count += 1
                logger.debug("Fixed Chest parent to Spine")
            
            if standard_upper_chest and keep_upper_chest:
                if standard_upper_chest.parent != standard_chest:
                    standard_upper_chest.parent = standard_chest
                    modified_count += 1
                    logger.debug("Fixed UpperChest parent to Chest")
            
            bpy.ops.object.mode_set(mode='OBJECT')
            return modified_count
        
        # Find all spine-like bones by pattern matching
        for edit_bone in edit_bones:
            bone_name = edit_bone.name
            bone_name_lower = bone_name.lower()
            
            # Check if this is a spine-like bone
            is_spine_like = False
            
            # Check spine patterns
            for pattern in SPINE_BONE_PATTERNS:
                if pattern.lower() in bone_name_lower or bone_name_lower == pattern.lower():
                    is_spine_like = True
                    break
            
            # Check chest patterns
            if not is_spine_like:
                for pattern in CHEST_BONE_PATTERNS:
                    if pattern.lower() in bone_name_lower:
                        is_spine_like = True
                        break
            
            # Check upper chest patterns
            if not is_spine_like:
                for pattern in UPPER_CHEST_PATTERNS:
                    if pattern.lower() in bone_name_lower:
                        is_spine_like = True
                        break
            
            if is_spine_like:
                spine_bones.append((bone_name, edit_bone))
        
        # Sort spine bones by hierarchy (parent first)
        def get_bone_depth(bone_tuple):
            bone = bone_tuple[1]
            depth = 0
            current = bone
            while current.parent:
                depth += 1
                current = current.parent
            return depth
        
        spine_bones.sort(key=get_bone_depth)
        
        num_spine_bones = len(spine_bones)
        logger.debug(f"Found {num_spine_bones} spine-like bones: {[b[0] for b in spine_bones]}")
        
        if num_spine_bones == 0:
            # No spine bones found, nothing to do
            bpy.ops.object.mode_set(mode='OBJECT')
            return 0
        
        elif num_spine_bones == 1:
            # 1 spine: Rename to Chest
            old_name = spine_bones[0][0]
            bone = spine_bones[0][1]
            
            if old_name != 'Chest':
                bone.name = 'Chest'
                modified_count += 1
                
                # Update vertex groups in meshes
                bpy.ops.object.mode_set(mode='OBJECT')
                for mesh in meshes:
                    if old_name in mesh.vertex_groups:
                        mesh.vertex_groups[old_name].name = 'Chest'
                bpy.ops.object.mode_set(mode='EDIT')
                
                logger.info(f"Renamed single spine bone {old_name} to Chest")
        
        elif num_spine_bones == 2:
            # 2 spines: First is Spine, second is Chest
            old_name_1 = spine_bones[0][0]
            old_name_2 = spine_bones[1][0]
            bone1 = spine_bones[0][1]
            bone2 = spine_bones[1][1]
            
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # Rename first to Spine
            if old_name_1 != 'Spine':
                bpy.ops.object.mode_set(mode='EDIT')
                if 'Spine' not in armature.data.edit_bones:
                    armature.data.edit_bones[old_name_1].name = 'Spine'
                    modified_count += 1
                bpy.ops.object.mode_set(mode='OBJECT')
                
                for mesh in meshes:
                    if old_name_1 in mesh.vertex_groups:
                        mesh.vertex_groups[old_name_1].name = 'Spine'
            
            # Rename second to Chest
            if old_name_2 != 'Chest':
                bpy.ops.object.mode_set(mode='EDIT')
                if 'Chest' not in armature.data.edit_bones:
                    armature.data.edit_bones[old_name_2].name = 'Chest'
                    modified_count += 1
                bpy.ops.object.mode_set(mode='OBJECT')
                
                for mesh in meshes:
                    if old_name_2 in mesh.vertex_groups:
                        mesh.vertex_groups[old_name_2].name = 'Chest'
            
            # Ensure parent relationship
            bpy.ops.object.mode_set(mode='EDIT')
            if 'Spine' in armature.data.edit_bones and 'Chest' in armature.data.edit_bones:
                armature.data.edit_bones['Chest'].parent = armature.data.edit_bones['Spine']
            
            logger.info("Set up 2-spine hierarchy: Spine -> Chest")
        
        elif num_spine_bones == 3:
            # 3 spines: Spine, Chest, Upper Chest
            old_names = [b[0] for b in spine_bones]
            
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # Rename bones
            rename_map = {
                old_names[0]: 'Spine',
                old_names[1]: 'Chest',
                old_names[2]: 'UpperChest' if keep_upper_chest else None
            }
            
            for old_name, new_name in rename_map.items():
                if new_name and old_name != new_name:
                    bpy.ops.object.mode_set(mode='EDIT')
                    if new_name not in armature.data.edit_bones and old_name in armature.data.edit_bones:
                        armature.data.edit_bones[old_name].name = new_name
                        modified_count += 1
                    bpy.ops.object.mode_set(mode='OBJECT')
                    
                    for mesh in meshes:
                        if old_name in mesh.vertex_groups:
                            mesh.vertex_groups[old_name].name = new_name
            
            # If not keeping upper chest, merge weights into Chest
            if not keep_upper_chest and old_names[2] != 'Chest':
                for mesh in meshes:
                    merge_vertex_group_weights(mesh, old_names[2], 'Chest')
                
                bpy.ops.object.mode_set(mode='EDIT')
                if old_names[2] in armature.data.edit_bones:
                    # Reparent children before removing
                    bone_to_remove = armature.data.edit_bones[old_names[2]]
                    chest_bone = armature.data.edit_bones.get('Chest')
                    if chest_bone:
                        for child in list(bone_to_remove.children):
                            child.parent = chest_bone
                    armature.data.edit_bones.remove(bone_to_remove)
                    modified_count += 1
                bpy.ops.object.mode_set(mode='OBJECT')
            
            # Ensure parent relationships
            bpy.ops.object.mode_set(mode='EDIT')
            edit_bones = armature.data.edit_bones
            if 'Spine' in edit_bones and 'Chest' in edit_bones:
                edit_bones['Chest'].parent = edit_bones['Spine']
            if keep_upper_chest and 'Chest' in edit_bones and 'UpperChest' in edit_bones:
                edit_bones['UpperChest'].parent = edit_bones['Chest']
            
            logger.info("Set up 3-spine hierarchy: Spine -> Chest -> UpperChest")
        
        else:
            # 4+ spines: Merge extras into proper structure
            old_names = [b[0] for b in spine_bones]
            
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # First three become Spine, Chest, UpperChest
            rename_map = {
                old_names[0]: 'Spine',
                old_names[1]: 'Chest',
                old_names[2]: 'UpperChest' if keep_upper_chest else 'Chest'
            }
            
            for old_name, new_name in rename_map.items():
                if old_name != new_name:
                    bpy.ops.object.mode_set(mode='EDIT')
                    if new_name not in armature.data.edit_bones and old_name in armature.data.edit_bones:
                        armature.data.edit_bones[old_name].name = new_name
                        modified_count += 1
                    bpy.ops.object.mode_set(mode='OBJECT')
                    
                    for mesh in meshes:
                        if old_name in mesh.vertex_groups:
                            mesh.vertex_groups[old_name].name = new_name
            
            # Merge extra spines into UpperChest (or Chest if not keeping upper chest)
            target_bone = 'UpperChest' if keep_upper_chest else 'Chest'
            
            for i in range(3, len(old_names)):
                extra_name = old_names[i]
                
                # Merge weights
                for mesh in meshes:
                    merge_vertex_group_weights(mesh, extra_name, target_bone)
                
                # Reparent children and remove bone
                bpy.ops.object.mode_set(mode='EDIT')
                if extra_name in armature.data.edit_bones:
                    bone_to_remove = armature.data.edit_bones[extra_name]
                    target = armature.data.edit_bones.get(target_bone)
                    if target:
                        for child in list(bone_to_remove.children):
                            child.parent = target
                    armature.data.edit_bones.remove(bone_to_remove)
                    modified_count += 1
                    logger.debug(f"Merged extra spine bone {extra_name} into {target_bone}")
                bpy.ops.object.mode_set(mode='OBJECT')
            
            # Ensure parent relationships
            bpy.ops.object.mode_set(mode='EDIT')
            edit_bones = armature.data.edit_bones
            if 'Spine' in edit_bones and 'Chest' in edit_bones:
                edit_bones['Chest'].parent = edit_bones['Spine']
            if keep_upper_chest and 'Chest' in edit_bones and 'UpperChest' in edit_bones:
                edit_bones['UpperChest'].parent = edit_bones['Chest']
            
            logger.info(f"Merged {len(old_names) - 3} extra spine bones into {target_bone}")
        
        bpy.ops.object.mode_set(mode='OBJECT')
        return modified_count
        
    except Exception as e:
        logger.error(f"Error fixing spine hierarchy: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
        return modified_count


def fix_missing_neck(context: Context, armature: Object) -> bool:
    """
    Fix missing Neck bone by creating one from Head if needed.
    
    Returns: True if neck was created/fixed, False otherwise
    """
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        edit_bones = armature.data.edit_bones
        
        # Check if Neck already exists
        neck_bone = None
        for pattern in NECK_BONE_PATTERNS:
            if pattern in edit_bones:
                neck_bone = edit_bones[pattern]
                break
        
        if neck_bone:
            # Neck exists, ensure it's named correctly
            if neck_bone.name != 'Neck':
                old_name = neck_bone.name
                neck_bone.name = 'Neck'
                
                bpy.ops.object.mode_set(mode='OBJECT')
                meshes = get_meshes_for_armature(armature)
                for mesh in meshes:
                    if old_name in mesh.vertex_groups:
                        mesh.vertex_groups[old_name].name = 'Neck'
                bpy.ops.object.mode_set(mode='EDIT')
                
                logger.info(f"Renamed {old_name} to Neck")
                bpy.ops.object.mode_set(mode='OBJECT')
                return True
            
            bpy.ops.object.mode_set(mode='OBJECT')
            return False
        
        # Neck doesn't exist, try to create from Head
        head_bone = None
        for pattern in HEAD_BONE_PATTERNS:
            if pattern in edit_bones:
                head_bone = edit_bones[pattern]
                break
        
        if not head_bone:
            logger.warning("Cannot create Neck: Head bone not found")
            bpy.ops.object.mode_set(mode='OBJECT')
            return False
        
        # Find the parent of Head (should be Chest or UpperChest)
        head_parent = head_bone.parent
        if not head_parent:
            logger.warning("Cannot create Neck: Head has no parent")
            bpy.ops.object.mode_set(mode='OBJECT')
            return False
        
        # Create Neck bone between Head's parent and Head
        neck = edit_bones.new('Neck')
        
        # Position Neck at 1/2 of the way from parent to Head
        parent_head_pos = head_parent.head
        head_head_pos = head_bone.head
        
        neck.head = parent_head_pos + (head_head_pos - parent_head_pos) * 0.5
        neck.tail = head_head_pos
        
        # Set up hierarchy
        neck.parent = head_parent
        head_bone.parent = neck
        
        # Copy roll from head
        neck.roll = head_bone.roll
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Create vertex group for Neck (empty, as weights will need manual assignment)
        meshes = get_meshes_for_armature(armature)
        for mesh in meshes:
            if 'Neck' not in mesh.vertex_groups:
                mesh.vertex_groups.new(name='Neck')
        
        logger.info("Created Neck bone between Head and its parent")
        return True
        
    except Exception as e:
        logger.error(f"Error fixing missing neck: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
        return False


def straighten_head_bone(context: Context, armature: Object) -> bool:
    """
    Straighten Head bone to align with world Z-axis.
    This improves appearance in T-pose and animation.
    
    Returns: True if head was straightened, False otherwise
    """
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        edit_bones = armature.data.edit_bones
        
        # Find Head bone
        head_bone = None
        for pattern in HEAD_BONE_PATTERNS:
            if pattern in edit_bones:
                head_bone = edit_bones[pattern]
                break
        
        if not head_bone:
            # Try standard name
            if 'Head' in edit_bones:
                head_bone = edit_bones['Head']
        
        if not head_bone:
            logger.warning("Cannot straighten head: Head bone not found")
            bpy.ops.object.mode_set(mode='OBJECT')
            return False
        
        # Calculate the desired direction (straight up in world Z)
        head_length = (head_bone.tail - head_bone.head).length
        
        # Set tail to be directly above head in Z direction
        new_tail = head_bone.head.copy()
        new_tail.z += head_length
        
        head_bone.tail = new_tail
        
        # Reset roll to 0 for proper alignment
        head_bone.roll = 0.0
        
        bpy.ops.object.mode_set(mode='OBJECT')
        logger.info("Straightened Head bone to align with world Z-axis")
        return True
        
    except Exception as e:
        logger.error(f"Error straightening head bone: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
        return False


def correct_arm_bone_positions(context: Context, armature: Object) -> int:
    """
    Correct arm bone positions for better T-pose appearance.
    Ensures arms are roughly horizontal and properly aligned.
    
    Returns: Number of bones adjusted
    """
    adjusted_count = 0
    
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        edit_bones = armature.data.edit_bones
        
        # Arm bone patterns for left and right
        arm_patterns = {
            'left': {
                'shoulder': ['LeftShoulder', 'Shoulder_L', 'shoulder_L', 'Left_Shoulder', 'shoulder.L'],
                'arm': ['LeftArm', 'Arm_L', 'arm_L', 'Left_Arm', 'UpperArm_L', 'arm.L'],
                'elbow': ['LeftElbow', 'Elbow_L', 'elbow_L', 'Left_Elbow', 'LowerArm_L', 'forearm.L'],
                'wrist': ['LeftWrist', 'Wrist_L', 'wrist_L', 'Left_Wrist', 'Hand_L', 'hand.L'],
            },
            'right': {
                'shoulder': ['RightShoulder', 'Shoulder_R', 'shoulder_R', 'Right_Shoulder', 'shoulder.R'],
                'arm': ['RightArm', 'Arm_R', 'arm_R', 'Right_Arm', 'UpperArm_R', 'arm.R'],
                'elbow': ['RightElbow', 'Elbow_R', 'elbow_R', 'Right_Elbow', 'LowerArm_R', 'forearm.R'],
                'wrist': ['RightWrist', 'Wrist_R', 'wrist_R', 'Right_Wrist', 'Hand_R', 'hand.R'],
            }
        }
        
        for side, patterns in arm_patterns.items():
            # Find arm bones
            arm_bone = None
            elbow_bone = None
            
            for pattern in patterns['arm']:
                if pattern in edit_bones:
                    arm_bone = edit_bones[pattern]
                    break
            
            for pattern in patterns['elbow']:
                if pattern in edit_bones:
                    elbow_bone = edit_bones[pattern]
                    break
            
            if not arm_bone or not elbow_bone:
                continue
            
            # Check if arm is roughly horizontal (within tolerance)
            arm_direction = (arm_bone.tail - arm_bone.head).normalized()
            
            # For a T-pose, arm should be mostly horizontal
            vertical_component = abs(arm_direction.z)
            
            # If the arm is too vertical (more than 30 degrees from horizontal)
            if vertical_component > 0.5:  # sin(30°) ≈ 0.5
                # Calculate the horizontal length
                arm_length = (arm_bone.tail - arm_bone.head).length
                
                # Determine direction based on side
                if side == 'left':
                    # Left arm typically points in +X
                    new_direction = Vector((1.0, 0.0, 0.0))
                else:
                    # Right arm points in -X
                    new_direction = Vector((-1.0, 0.0, 0.0))
                
                # Set new tail position
                arm_bone.tail = arm_bone.head + new_direction * arm_length
                adjusted_count += 1
                logger.debug(f"Adjusted {side} arm bone to be more horizontal")
            
            # Similarly check elbow
            elbow_direction = (elbow_bone.tail - elbow_bone.head).normalized()
            vertical_component = abs(elbow_direction.z)
            
            if vertical_component > 0.5:
                elbow_length = (elbow_bone.tail - elbow_bone.head).length
                
                if side == 'left':
                    new_direction = Vector((1.0, 0.0, 0.0))
                else:
                    new_direction = Vector((-1.0, 0.0, 0.0))
                
                elbow_bone.tail = elbow_bone.head + new_direction * elbow_length
                adjusted_count += 1
                logger.debug(f"Adjusted {side} elbow bone to be more horizontal")
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
        if adjusted_count > 0:
            logger.info(f"Adjusted {adjusted_count} arm bones for better T-pose")
        
        return adjusted_count
        
    except Exception as e:
        logger.error(f"Error correcting arm bone positions: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
        return adjusted_count
