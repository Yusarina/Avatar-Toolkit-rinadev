# GPL License
# Avatar Toolkit MMD Converter - Main Operator

import bpy
import traceback
from typing import Set, List, Dict, Any, ClassVar
from bpy.types import Operator, Context, Object

from ....core.logging_setup import logger
from ....core.translations import t
from ....core.common import (
    get_active_armature,
    get_meshes_for_armature,
    fix_zero_length_bones,
    store_breaking_settings_armature,
    restore_breaking_settings_armature,
    SavedData,
    set_active,
    unselect_all,
    unhide_all,
    get_objects,
    clear_unused_data_blocks,
)
from ....core.mmd.translations import translateFromJp, jp_half_to_full_tuples

# Import modular components
from .validation import MMDArmatureValidator
from .bone_cache import BoneCache
from .mmd_handlers import MMDRootHandler, BoneMorphConverter
from .dictionary_builder import BoneDictionaryBuilder

# Import phase functions
from .phase_mesh import (
    remove_duplicate_armature_modifiers,
    ensure_armature_modifier,
    clean_mesh_shapekeys,
    ensure_mesh_parenting,
    fix_material_names,
    join_child_meshes,
    contains_japanese,
)

from .phase_bones import (
    translate_bone_names,
    translate_shapekey_names,
    translate_object_names,
    rename_bones_from_dictionary,
    unhide_all_bones,
    reset_pose_position,
    remove_all_bone_collections,
    delete_all_bone_constraints,
    reset_bone_visibility,
    clean_bone_name_prefixes,
    standardize_side_indicators,
    rename_bones_with_dictionary,
    resolve_conflicting_bone_names,
)

from .phase_hierarchy import (
    remove_twist_bones,
    remove_end_bones,
    disconnect_bones_and_reset_roll,
    fix_bone_hierarchy,
)

from .phase_special import (
    fix_spine_hierarchy,
    fix_missing_neck,
    straighten_head_bone,
    correct_arm_bone_positions,
)

from .phase_eyes import (
    process_eye_bones,
    reweight_eye_children,
    ensure_eye_bone_hierarchy,
)

from .phase_weights import (
    process_reweight_dictionary,
    merge_finger_weights,
    handle_twist_bone_weights,
    cleanup_unused_vertex_groups,
)

from .phase_cleanup import (
    delete_merged_bones,
    fix_bone_parenting_for_unity,
    standardize_twist_bone_names,
    remove_zero_weight_bones,
    connect_bones_to_children,
    fix_armature_name,
)

from .phase_completion import (
    restore_state,
    switch_to_object_mode,
    display_completion_message,
    finalize_armature,
    cleanup_scene,
)


class AvatarToolkit_OT_FixMMDArmature(Operator):
    """Fix MMD armature for VRChat/Unity compatibility"""
    bl_idname: ClassVar[str] = "avatar_toolkit.fix_mmd_armature"
    bl_label: ClassVar[str] = t("MMD.fix_armature.label")
    bl_description: ClassVar[str] = t("MMD.fix_armature.desc")
    bl_options: ClassVar[Set[str]] = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context) -> bool:
        armature = get_active_armature(context)
        if not armature:
            return False
        return armature.type == 'ARMATURE'

    def execute(self, context: Context) -> Set[str]:
        armature = get_active_armature(context)
        toolkit = context.scene.avatar_toolkit
        
        logger.info(f"Starting MMD armature fix for: {armature.name}")
        
        # PHASE 1: Validation & Setup
        saved_data = SavedData()
        
        errors, warnings = MMDArmatureValidator.validate_armature_requirements(context, armature)
        
        for warning in warnings:
            self.report({'WARNING'}, warning)
            logger.warning(warning)
        
        if errors:
            for error in errors:
                self.report({'ERROR'}, error)
                logger.error(error)
            return {'CANCELLED'}
        
        if MMDArmatureValidator._is_rigify_armature(armature):
            self.report({'ERROR'}, t("MMD.validation.rigify_detected"))
            return {'CANCELLED'}
        
        bone_cache = BoneCache(armature)
        logger.debug(f"Bone cache initialized with {len(bone_cache.bone_name_map)} bones")
        
        mmd_root = MMDRootHandler.get_mmd_root(armature)
        bone_collections_backup: List[Dict[str, Any]] = []
        
        if mmd_root:
            logger.info("MMD model detected")
            bone_collections_backup = MMDRootHandler.backup_bone_collections(armature)
            logger.debug(f"Backed up {len(bone_collections_backup)} bone collections")
        else:
            logger.info("Non-MMD model - some MMD-specific features will be skipped")
        
        multi_user_meshes = MMDArmatureValidator.check_single_user_meshes(armature)
        if multi_user_meshes:
            mesh_names = ', '.join([m.name for m in multi_user_meshes])
            self.report({'WARNING'}, t("MMD.validation.multi_user_meshes", meshes=mesh_names))
            logger.warning(f"Multi-user meshes detected: {mesh_names}")
            for mesh in multi_user_meshes:
                mesh.data = mesh.data.copy()
                logger.debug(f"Made {mesh.name} single-user")
        
        try:
            data_breaking = store_breaking_settings_armature(armature)
            
            # PHASE 2: Model Type Detection & Preparation
            unhide_all()
            unselect_all()
            
            for obj in get_objects():
                if obj.mode != 'OBJECT':
                    set_active(obj, skip_sel=True)
                    bpy.ops.object.mode_set(mode='OBJECT')
                    unselect_all()
            
            set_active(armature)
            
            rename_dict = BoneDictionaryBuilder.build_rename_dictionary()
            reweight_dict = BoneDictionaryBuilder.build_reweight_dictionary(rename_dict)
            total_steps = BoneDictionaryBuilder.count_processing_steps(rename_dict, reweight_dict, armature)
            
            logger.debug(f"Prepared dictionaries - rename: {len(rename_dict)}, reweight: {len(reweight_dict)}")
            logger.debug(f"Total processing steps: {total_steps}")
            
            if mmd_root:
                self._handle_mmd_operations(context, armature, mmd_root, toolkit)
            
            self._handle_blenda_quirk(armature)
            self._remove_unused_animations(armature)
            
            # PHASE 3: Scene & Transform Setup
            if toolkit.mmd_remove_rigidbodies:
                removed_rb = self._remove_rigidbodies_and_joints(armature)
                if removed_rb > 0:
                    logger.info(f"Removed {removed_rb} rigidbody/joint objects")
            
            self._fix_fbx_scaling(context, armature)
            fix_zero_length_bones(armature)
            logger.debug("Fixed zero-length bones")
            
            if toolkit.mmd_apply_transforms:
                set_active(armature)
                bpy.ops.avatar_toolkit.apply_transforms()
                logger.debug("Applied transforms using ATK operator")
            
            if toolkit.mmd_join_meshes:
                join_child_meshes(context, armature)
            
            self._unlock_all_transforms(armature)
            self._remove_empty_and_unused(context, armature)
            
            # PHASE 4: Mesh Processing
            meshes = get_meshes_for_armature(armature)
            
            if meshes:
                logger.info(f"Processing {len(meshes)} mesh(es)")
                
                for mesh in meshes:
                    logger.debug(f"Processing mesh: {mesh.name}")
                    remove_duplicate_armature_modifiers(mesh, armature)
                    ensure_armature_modifier(mesh, armature)
                    clean_mesh_shapekeys(mesh)
                    ensure_mesh_parenting(mesh, armature)
                    
                    if toolkit.mmd_translate_materials:
                        fix_material_names(mesh)
                
                if toolkit.mmd_remove_doubles:
                    try:
                        set_active(armature)
                        bpy.ops.avatar_toolkit.remove_doubles('INVOKE_DEFAULT', merge_distance=0.0001)
                        logger.info("Invoked ATK remove doubles operator")
                    except Exception as e:
                        logger.warning(f"Could not invoke remove doubles operator: {e}")
            else:
                logger.warning("No meshes found for armature")
            
            # PHASE 5: Bone Translation & Visibility
            logger.info("Starting Phase 5: Bone Translation & Visibility")
            
            renamed_count = rename_bones_from_dictionary(context, armature, rename_dict)
            logger.info(f"Renamed {renamed_count} bones using dictionary")
            
            unhide_all_bones(armature)
            logger.debug("Unhid all bones")
            
            reset_pose_position(armature)
            logger.debug("Reset pose position")
            
            # PHASE 6: Bone Cleanup
            logger.info("Starting Phase 6: Bone Cleanup")
            
            removed = remove_all_bone_collections(armature)
            if removed > 0:
                logger.info(f"Removed {removed} bone collections")
            
            if toolkit.mmd_delete_bone_constraints:
                removed = delete_all_bone_constraints(armature)
                if removed > 0:
                    logger.info(f"Deleted {removed} bone constraints")
            
            reset_bone_visibility(armature)
            logger.debug("Reset bone visibility for all bones")
            
            # PHASE 7: Bone Name Standardization
            logger.info("Starting Phase 7: Bone Name Standardization")
            
            cleaned = clean_bone_name_prefixes(context, armature)
            if cleaned > 0:
                logger.info(f"Cleaned {cleaned} bone name prefixes/suffixes")
            
            standardized = standardize_side_indicators(context, armature)
            if standardized > 0:
                logger.info(f"Standardized {standardized} bone side indicators")
            
            renamed = rename_bones_with_dictionary(context, armature)
            if renamed > 0:
                logger.info(f"Renamed {renamed} bones using dictionary")
            
            resolved = resolve_conflicting_bone_names(context, armature)
            if resolved > 0:
                logger.info(f"Resolved {resolved} conflicting bone names")
            
            # PHASE 8: Bone Hierarchy Fixing
            logger.info("Starting Phase 8: Bone Hierarchy Fixing")
            
            if toolkit.mmd_remove_twist_bones:
                removed = remove_twist_bones(context, armature)
                if removed > 0:
                    logger.info(f"Removed {removed} twist bones")
            
            if toolkit.mmd_remove_end_bones:
                removed_end = remove_end_bones(context, armature)
                if removed_end > 0:
                    logger.info(f"Removed {removed_end} end bones")
            
            disconnect_bones_and_reset_roll(context, armature)
            logger.debug("Disconnected bones and reset roll")
            
            fix_bone_hierarchy(context, armature)
            logger.debug("Fixed bone hierarchy - Hips is now top parent")
            
            # PHASE 9: Special Bone Fixes
            logger.info("Starting Phase 9: Special Bone Fixes")
            
            spine_fixed = fix_spine_hierarchy(context, armature, 
                                              keep_upper_chest=toolkit.keep_upper_chest)
            if spine_fixed > 0:
                logger.info(f"Fixed {spine_fixed} spine hierarchy bones")
            
            neck_fixed = fix_missing_neck(context, armature)
            if neck_fixed:
                logger.info("Fixed/created Neck bone")
            
            head_straightened = straighten_head_bone(context, armature)
            if head_straightened:
                logger.info("Straightened Head bone")
            
            arms_corrected = correct_arm_bone_positions(context, armature)
            if arms_corrected > 0:
                logger.info(f"Corrected {arms_corrected} arm bone positions")
            
            # PHASE 10: Eye Bone Processing
            logger.info("Starting Phase 10: Eye Bone Processing")
            
            eyes_processed = process_eye_bones(context, armature)
            if eyes_processed > 0:
                logger.info(f"Processed {eyes_processed} eye bones")
            
            eye_weights = reweight_eye_children(context, armature)
            if eye_weights > 0:
                logger.info(f"Transferred {eye_weights} eye child weights")
            
            eye_hierarchy_fixed = ensure_eye_bone_hierarchy(context, armature)
            if eye_hierarchy_fixed:
                logger.info("Fixed eye bone hierarchy")
            
            # PHASE 11: Weight Merging
            logger.info("Starting Phase 11: Weight Merging")
            
            # Process reweight dictionary
            weights_transferred = process_reweight_dictionary(
                context, armature, reweight_dict,
                threshold=toolkit.merge_weights_threshold if hasattr(toolkit, 'merge_weights_threshold') else 0.01
            )
            if weights_transferred > 0:
                logger.info(f"Transferred {weights_transferred} vertex group weights")
            
            # Handle finger weights
            finger_weights = merge_finger_weights(context, armature)
            if finger_weights > 0:
                logger.info(f"Merged {finger_weights} finger bone weights")
            
            # Handle twist bone weights (if merging enabled)
            if hasattr(toolkit, 'merge_twist_bones') and toolkit.merge_twist_bones:
                twist_weights = handle_twist_bone_weights(context, armature, merge_twist=True)
                if twist_weights > 0:
                    logger.info(f"Merged {twist_weights} twist bone weights")
            
            # Cleanup unused vertex groups
            unused_removed = cleanup_unused_vertex_groups(context, armature)
            if unused_removed > 0:
                logger.info(f"Removed {unused_removed} unused vertex groups")
            
            # PHASE 12: Final Cleanup
            logger.info("Starting Phase 12: Final Cleanup")
            
            # Collect bones that were reweighted and can be deleted
            bones_to_delete = []
            for target_bone, source_bones in reweight_dict.items():
                for source_bone in source_bones:
                    if source_bone != target_bone and source_bone not in bones_to_delete:
                        # Check if bone exists and has no weights
                        if source_bone in [b.name for b in armature.data.bones]:
                            bones_to_delete.append(source_bone)
            
            # Delete merged bones (only if they have no remaining weights)
            # This is handled conservatively - only delete if explicitly merged
            
            # Fix bone parenting for Unity/VRChat
            reparented = fix_bone_parenting_for_unity(context, armature)
            if reparented > 0:
                logger.info(f"Reparented {reparented} bones for Unity compatibility")
            
            # Standardize twist bone names (if keeping twist bones)
            if hasattr(toolkit, 'keep_twist_bones') and toolkit.keep_twist_bones:
                twist_renamed = standardize_twist_bone_names(context, armature)
                if twist_renamed > 0:
                    logger.info(f"Standardized {twist_renamed} twist bone names")
            
            # Remove zero-weight bones (if option enabled)
            if hasattr(toolkit, 'mmd_remove_zero_weight_bones') and toolkit.mmd_remove_zero_weight_bones:
                zero_weight_removed = remove_zero_weight_bones(context, armature)
                if zero_weight_removed > 0:
                    logger.info(f"Removed {zero_weight_removed} zero-weight bones")
            
            # Connect bones to children (if option enabled)
            if hasattr(toolkit, 'mmd_connect_bones') and toolkit.mmd_connect_bones:
                connected = connect_bones_to_children(context, armature)
                if connected > 0:
                    logger.info(f"Connected {connected} bones to children")
            
            # Fix armature name (if option enabled)
            if hasattr(toolkit, 'mmd_rename_armature') and toolkit.mmd_rename_armature:
                if fix_armature_name(armature, "Armature"):
                    logger.info("Renamed armature to 'Armature'")
            
            # PHASE 13: Completion
            logger.info("Starting Phase 13: Completion")
            
            # Store dictionaries for potential future use
            context.scene['_mmd_fixer_rename_dict'] = str(rename_dict)
            context.scene['_mmd_fixer_reweight_dict'] = str(reweight_dict)
            
            # Restore armature settings
            restore_breaking_settings_armature(armature, data_breaking)
            
            # Finalize armature
            finalize_armature(context, armature)
            
            # Switch to object mode
            switch_to_object_mode(context)
            
            # Cleanup scene
            cleanup_scene(context)
            
            # Restore state
            restore_state(context, saved_data, armature)
            
            # Clean up bone cache
            bone_cache.clear_cache()
            
            # Build stats for completion message
            stats = {
                'bones_renamed': renamed,
                'weights_transferred': weights_transferred,
                'bones_removed': 0,  # Could track this more precisely
            }
            
            display_completion_message(self, success=True, stats=stats)
            logger.info("MMD armature fix completed successfully (Phases 1-13)")
            return {'FINISHED'}
            
        except Exception as e:
            logger.error(f"MMD armature fix failed: {traceback.format_exc()}")
            self.report({'ERROR'}, f"Fix failed: {str(e)}")
            bone_cache.clear_cache()
            return {'CANCELLED'}

    def _handle_mmd_operations(self, context: Context, armature: Object, 
                               mmd_root: Any, toolkit: Any) -> None:
        """Handle MMD-specific operations including translations and cleanup"""
        logger.info("Processing MMD-specific operations")
        
        try:
            if hasattr(mmd_root, 'use_toon_texture'):
                mmd_root.use_toon_texture = False
            if hasattr(mmd_root, 'use_sphere_texture'):
                mmd_root.use_sphere_texture = False
        except Exception as e:
            logger.debug(f"Could not disable toon/sphere textures: {e}")
        
        if hasattr(mmd_root, 'bone_morphs') and len(mmd_root.bone_morphs) > 0:
            logger.info(f"Converting {len(mmd_root.bone_morphs)} bone morphs to shape keys")
            
            try:
                bpy.ops.mmd_tools.convert_bone_morph_to_vertex_morph()
                logger.info("Converted bone morphs using mmd_tools operator")
            except Exception as e:
                logger.debug(f"mmd_tools operator not available: {e}")
                converted = BoneMorphConverter.convert_bone_morphs_to_shapekeys(
                    context, armature, mmd_root
                )
                logger.info(f"Converted {converted} bone morphs using native method")
        
        if toolkit.mmd_translate_names and toolkit.mmd_translate_bones:
            translated = translate_bone_names(armature)
            logger.info(f"Translated {translated} bone names")
        
        if toolkit.mmd_translate_names and toolkit.mmd_translate_shapekeys:
            translated = translate_shapekey_names(armature)
            logger.info(f"Translated {translated} shape key names")
        
        if toolkit.mmd_translate_names and toolkit.mmd_translate_objects:
            translated = translate_object_names(armature)
            logger.info(f"Translated {translated} object names")
        
        self._cleanup_mmd_data(context, armature, mmd_root)
        
        removed_collections = MMDRootHandler.remove_bone_collections(armature)
        if removed_collections > 0:
            logger.debug(f"Removed {removed_collections} bone collections")

    def _handle_blenda_quirk(self, armature: Object) -> None:
        """Handle 'Blenda' model quirk where Spine1 represents hips."""
        is_blenda_model = False
        
        for bone in armature.pose.bones:
            if bone.name == 'Spine1' and bone.parent and bone.parent.name == 'Root':
                is_blenda_model = True
                break
        
        if not is_blenda_model:
            return
        
        logger.info("Detected Blenda model quirk - renaming Spine1 to BlendaHips")
        
        try:
            set_active(armature)
            bpy.ops.object.mode_set(mode='EDIT')
            
            if 'Spine1' in armature.data.edit_bones:
                edit_bone = armature.data.edit_bones['Spine1']
                edit_bone.name = 'BlendaHips'
                logger.debug("Renamed Spine1 to BlendaHips")
                
                meshes = get_meshes_for_armature(armature)
                for mesh in meshes:
                    if 'Spine1' in mesh.vertex_groups:
                        mesh.vertex_groups['Spine1'].name = 'BlendaHips'
            
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception as e:
            logger.warning(f"Could not rename Blenda Spine1 bone: {e}")
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except:
                pass

    def _remove_unused_animations(self, armature: Object) -> None:
        """Remove unused animation data like ragdoll actions"""
        if armature.animation_data and armature.animation_data.action:
            action_name = armature.animation_data.action.name
            if action_name == 'ragdoll':
                logger.info("Removing unused ragdoll animation")
                armature.animation_data.action = None

    def _cleanup_mmd_data(self, context: Context, armature: Object, mmd_root: Any) -> None:
        """Clean up MMD-specific data that may cause issues."""
        logger.debug("Cleaning up MMD-specific data")
        
        if hasattr(mmd_root, 'bone_order'):
            try:
                mmd_root.bone_order.clear()
                logger.debug("Cleared MMD bone order")
            except Exception as e:
                logger.debug(f"Could not clear bone order: {e}")
        
        if hasattr(mmd_root, 'uv_morphs'):
            for uv_morph in mmd_root.uv_morphs:
                if hasattr(uv_morph, 'data_type') and uv_morph.data_type == 'VERTEX_GROUP':
                    meshes = get_meshes_for_armature(armature)
                    for mesh in meshes:
                        vg_to_remove = [vg.name for vg in mesh.vertex_groups 
                                       if vg.name.startswith(f"UV_{uv_morph.name}")]
                        for vg_name in vg_to_remove:
                            mesh.vertex_groups.remove(mesh.vertex_groups[vg_name])
        
        for bone in armature.pose.bones:
            for constraint in bone.constraints:
                if constraint.type == 'IK':
                    constraint.mute = True
        
        logger.debug("MMD data cleanup complete")

    def _remove_rigidbodies_and_joints(self, armature: Object) -> int:
        """Remove rigidbodies and joints associated with an armature."""
        removed_count = 0
        to_delete: List[Object] = []
        
        parent: Object = armature
        while parent.parent:
            parent = parent.parent
        
        def find_physics_objects(obj: Object) -> None:
            name_lower = obj.name.lower()
            if 'rigidbodies' in name_lower or 'joints' in name_lower or \
               'rigidbody' in name_lower or 'joint' in name_lower or \
               '剛体' in obj.name or 'Joint' in obj.name:
                to_delete.append(obj)
            for child in obj.children:
                find_physics_objects(child)
        
        find_physics_objects(parent)
        
        for child in armature.children:
            name_lower = child.name.lower()
            if 'rigidbodies' in name_lower or 'joints' in name_lower or \
               'rigidbody' in name_lower or 'joint' in name_lower:
                if child not in to_delete:
                    to_delete.append(child)
        
        for obj in to_delete:
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
                removed_count += 1
            except Exception as e:
                logger.warning(f"Could not remove physics object {obj.name}: {e}")
        
        return removed_count

    def _fix_fbx_scaling(self, context: Context, armature: Object) -> None:
        """Handle weird FBX scaling where models are scaled to 0.01."""
        if (round(armature.scale[0], 2) == 0.01 and
            round(armature.scale[1], 2) == 0.01 and
            round(armature.scale[2], 2) == 0.01):
            
            logger.info("Detected FBX 0.01 scaling - fixing transforms")
            armature.scale = (1.0, 1.0, 1.0)
            
            meshes = get_meshes_for_armature(armature)
            for mesh in meshes:
                if (round(mesh.scale[0], 2) == 0.01 and
                    round(mesh.scale[1], 2) == 0.01 and
                    round(mesh.scale[2], 2) == 0.01):
                    mesh.scale = (1.0, 1.0, 1.0)

    def _unlock_all_transforms(self, armature: Object) -> None:
        """Unlock all transforms on armature and its bones."""
        for i in range(3):
            armature.lock_location[i] = False
            armature.lock_rotation[i] = False
            armature.lock_scale[i] = False
        
        for bone in armature.pose.bones:
            for i in range(3):
                bone.lock_location[i] = False
                bone.lock_rotation[i] = False
                bone.lock_scale[i] = False
            
            if hasattr(bone, 'lock_rotation_w'):
                bone.lock_rotation_w = False
            
            if hasattr(bone, 'lock_ik_x'):
                bone.lock_ik_x = False
                bone.lock_ik_y = False
                bone.lock_ik_z = False
        
        logger.debug("Unlocked all transforms on armature and bones")

    def _remove_empty_and_unused(self, context: Context, armature: Object) -> None:
        """Remove empty MMD object and other unused objects."""
        if armature.parent and armature.parent.type == 'EMPTY':
            empty_parent = armature.parent
            
            is_mmd_empty = (hasattr(empty_parent, 'mmd_root') or 
                           hasattr(empty_parent, 'mmd_type') or
                           'mmd' in empty_parent.name.lower())
            
            if is_mmd_empty:
                matrix_world = armature.matrix_world.copy()
                armature.parent = None
                armature.matrix_world = matrix_world
                
                for child in list(empty_parent.children):
                    if child != armature and child.type == 'MESH':
                        child.parent = armature
                
                try:
                    bpy.data.objects.remove(empty_parent, do_unlink=True)
                    logger.info("Removed MMD parent empty object")
                except Exception as e:
                    logger.warning(f"Could not remove MMD empty: {e}")
        
        self._remove_default_objects()
        
        try:
            cleared = clear_unused_data_blocks()
            if cleared > 0:
                logger.debug(f"Cleared {cleared} unused data blocks")
        except Exception as e:
            logger.debug(f"Could not clear unused data blocks: {e}")

    def _remove_default_objects(self) -> None:
        """Remove default Blender objects (Cube, Light, Camera) if present"""
        default_names = {'Cube', 'Light', 'Camera', 'Lamp'}
        
        for obj in list(bpy.data.objects):
            base_name = obj.name.split('.')[0]
            if base_name in default_names:
                if obj.type == 'MESH' and base_name == 'Cube':
                    if len(obj.data.vertices) == 8: 
                        try:
                            bpy.data.objects.remove(obj, do_unlink=True)
                        except:
                            pass
                elif obj.type in {'LIGHT', 'LAMP'} and base_name in {'Light', 'Lamp'}:
                    try:
                        bpy.data.objects.remove(obj, do_unlink=True)
                    except:
                        pass
                elif obj.type == 'CAMERA' and base_name == 'Camera':
                    try:
                        bpy.data.objects.remove(obj, do_unlink=True)
                    except:
                        pass
