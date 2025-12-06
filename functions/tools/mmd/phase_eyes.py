# GPL License
# Avatar Toolkit MMD Converter - Eye Bone Processing (Phase 10)

import bpy
from typing import Dict, List
from bpy.types import Context, Object

from ....core.logging_setup import logger
from ....core.common import get_meshes_for_armature, set_active

from .phase_hierarchy import merge_vertex_group_weights
from .phase_special import HEAD_BONE_PATTERNS


# Eye bone patterns
EYE_BONE_PATTERNS: Dict[str, List[str]] = {
    'left': [
        'Eye_L', 'eye_L', 'LeftEye', 'Eye.L', 'eye.L', 'EyeL', 'eyeL',
        'Left_Eye', 'left_eye', 'L_Eye', 'l_eye',
        '左目', '目_L', '目.L',
    ],
    'right': [
        'Eye_R', 'eye_R', 'RightEye', 'Eye.R', 'eye.R', 'EyeR', 'eyeR', 
        'Right_Eye', 'right_eye', 'R_Eye', 'r_eye',
        '右目', '目_R', '目.R',
    ]
}


def process_eye_bones(context: Context, armature: Object) -> int:
    """
    Process eye bones:
    1. Find Eye_L and Eye_R bones
    2. Reweight eye children into the eye bones themselves
    3. Ensure proper eye bone naming
    
    Returns: Number of eye bones processed
    """
    meshes = get_meshes_for_armature(armature)
    processed_count = 0
    
    try:
        set_active(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        
        edit_bones = armature.data.edit_bones
        
        for side, patterns in EYE_BONE_PATTERNS.items():
            eye_bone = None
            eye_bone_name = None
            
            # Find eye bone
            for pattern in patterns:
                if pattern in edit_bones:
                    eye_bone = edit_bones[pattern]
                    eye_bone_name = pattern
                    break
            
            if not eye_bone:
                continue
            
            # Standard name for this eye
            standard_name = 'Eye_L' if side == 'left' else 'Eye_R'
            
            # Rename if needed
            if eye_bone_name != standard_name:
                # Check if standard name already exists
                if standard_name not in edit_bones:
                    old_name = eye_bone_name
                    eye_bone.name = standard_name
                    
                    bpy.ops.object.mode_set(mode='OBJECT')
                    
                    # Update vertex groups
                    for mesh in meshes:
                        if old_name in mesh.vertex_groups:
                            mesh.vertex_groups[old_name].name = standard_name
                    
                    bpy.ops.object.mode_set(mode='EDIT')
                    eye_bone_name = standard_name
                    processed_count += 1
                    logger.debug(f"Renamed {old_name} to {standard_name}")
            
            # Get children of eye bone
            eye_children = list(eye_bone.children)
            
            if eye_children:
                logger.debug(f"Found {len(eye_children)} children of {eye_bone_name}")
                
                # Collect child names before modifying
                child_names = [child.name for child in eye_children]
                
                bpy.ops.object.mode_set(mode='OBJECT')
                
                # Merge weights from children into eye bone
                for child_name in child_names:
                    for mesh in meshes:
                        merge_vertex_group_weights(mesh, child_name, eye_bone_name)
                    logger.debug(f"Merged weights from {child_name} into {eye_bone_name}")
                
                bpy.ops.object.mode_set(mode='EDIT')
                
                # Refresh edit_bones reference after mode switch
                edit_bones = armature.data.edit_bones
                
                # Remove child bones
                for child_name in child_names:
                    if child_name in edit_bones:
                        child_bone = edit_bones[child_name]
                        
                        # First, reparent any grandchildren to the eye bone
                        # Check if eye bone still exists before reparenting
                        if eye_bone_name in edit_bones:
                            for grandchild in list(child_bone.children):
                                grandchild.parent = edit_bones[eye_bone_name]
                        
                        edit_bones.remove(child_bone)
                        logger.debug(f"Removed eye child bone: {child_name}")
                
                processed_count += 1
            
            processed_count += 1
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
        if processed_count > 0:
            logger.info(f"Processed {processed_count} eye bones")
        
        return processed_count
        
    except Exception as e:
        logger.error(f"Error processing eye bones: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
        return processed_count


def reweight_eye_children(context: Context, armature: Object) -> int:
    """
    Specifically reweight eye bone children into the eye bones.
    This is useful for models that have separate bones for iris, pupil, etc.
    
    Returns: Number of weight transfers performed
    """
    meshes = get_meshes_for_armature(armature)
    transfer_count = 0
    
    try:
        set_active(armature)
        
        # Work in object mode for vertex group operations
        bpy.ops.object.mode_set(mode='OBJECT')
        
        for side, patterns in EYE_BONE_PATTERNS.items():
            eye_bone_name = None
            
            # Find the eye bone
            for pattern in patterns:
                if pattern in armature.data.bones:
                    eye_bone_name = pattern
                    break
            
            if not eye_bone_name:
                continue
            
            eye_bone = armature.data.bones[eye_bone_name]
            
            # Get all children recursively
            def get_all_children(bone):
                children = list(bone.children)
                all_children = list(children)
                for child in children:
                    all_children.extend(get_all_children(child))
                return all_children
            
            all_eye_children = get_all_children(eye_bone)
            
            for child_bone in all_eye_children:
                child_name = child_bone.name
                
                # Merge weights into eye bone
                for mesh in meshes:
                    if child_name in mesh.vertex_groups:
                        merge_vertex_group_weights(mesh, child_name, eye_bone_name)
                        transfer_count += 1
                        logger.debug(f"Transferred weights from {child_name} to {eye_bone_name}")
        
        return transfer_count
        
    except Exception as e:
        logger.error(f"Error reweighting eye children: {e}")
        return transfer_count


def ensure_eye_bone_hierarchy(context: Context, armature: Object) -> bool:
    """
    Ensure eye bones are properly parented to Head bone.
    
    Returns: True if hierarchy was fixed, False otherwise
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
            if 'Head' in edit_bones:
                head_bone = edit_bones['Head']
        
        if not head_bone:
            logger.warning("Cannot fix eye hierarchy: Head bone not found")
            bpy.ops.object.mode_set(mode='OBJECT')
            return False
        
        fixed = False
        
        # Check and fix each eye
        for side, patterns in EYE_BONE_PATTERNS.items():
            eye_bone = None
            
            for pattern in patterns:
                if pattern in edit_bones:
                    eye_bone = edit_bones[pattern]
                    break
            
            if eye_bone and eye_bone.parent != head_bone:
                eye_bone.parent = head_bone
                fixed = True
                logger.debug(f"Reparented {eye_bone.name} to {head_bone.name}")
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
        if fixed:
            logger.info("Fixed eye bone hierarchy - eyes now parented to Head")
        
        return fixed
        
    except Exception as e:
        logger.error(f"Error ensuring eye bone hierarchy: {e}")
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
        return False
