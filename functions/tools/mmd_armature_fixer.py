# GPL License
# Avatar Toolkit MMD Converter

import bpy
import copy
import traceback
from typing import Set, List, Tuple, Dict, Optional, Any, ClassVar
from bpy.types import Operator, Context, Object, Armature, EditBone, PoseBone, Modifier
from mathutils import Vector, Matrix, Quaternion

from ...core.logging_setup import logger
from ...core.translations import t
from ...core.common import (
    get_active_armature,
    get_all_meshes,
    get_meshes_for_armature,
    get_meshes_objects,
    validate_meshes,
    ProgressTracker,
    remove_unused_vertex_groups,
    fix_zero_length_bones,
    store_breaking_settings_armature,
    restore_breaking_settings_armature,
    SavedData,
    set_active,
    unselect_all,
    unhide_all,
    get_objects,
    is_hidden,
    hide,
    select,
    clear_unused_data_blocks,
    clean_shapekeys,
    has_shapekeys,
    add_armature_modifier,
)
from ...core.armature_validation import validate_armature, is_pmx_model
from ...core.mmd.translations import translateFromJp, getTranslator, jp_to_en_tuples, jp_half_to_full_tuples
from ...core.dictionaries import bone_names, reverse_bone_lookup, simplify_bonename
from ...core.enhanced_dictionaries import (
    mmd_bone_rename,
    mmd_bone_reweight,
    mmd_finger_patterns,
)


# VALIDATION SYSTEM

class MMDValidationError(Exception):
    """Custom exception for MMD validation errors"""
    def __init__(self, message: str, error_code: Optional[str] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class MMDArmatureValidator:
    """Comprehensive validation for MMD armature fixing operations"""
    
    @staticmethod
    def validate_armature_requirements(context: Context, armature: Object) -> Tuple[List[str], List[str]]:
        """
        Validate all requirements before processing begins.
        
        Returns:
            Tuple of (errors, warnings) - errors should stop processing, warnings are informational
        """
        errors: List[str] = []
        warnings: List[str] = []
        
        # Basic armature validation
        if not armature:
            errors.append(t("MMD.validation.no_armature"))
            return errors, warnings
            
        if not armature.data:
            errors.append(t("MMD.validation.no_armature_data"))
            return errors, warnings
        
        # Check for locked transforms
        if any(armature.lock_location) or any(armature.lock_rotation) or any(armature.lock_scale):
            warnings.append(t("MMD.validation.locked_transforms"))
        
        # Check bone count
        bone_count = len(armature.data.bones)
        if bone_count == 0:
            errors.append(t("MMD.validation.no_bones"))
        elif bone_count > 1000:
            warnings.append(t("MMD.validation.many_bones", count=bone_count))
        
        # Check for Rigify/Metarig (should use different converter)
        if MMDArmatureValidator._is_rigify_armature(armature):
            errors.append(t("MMD.validation.rigify_detected"))
        
        # Validate meshes
        mesh_errors, mesh_warnings = MMDArmatureValidator._validate_meshes(context, armature)
        errors.extend(mesh_errors)
        warnings.extend(mesh_warnings)
        
        # Check if actually MMD model
        if not MMDArmatureValidator._is_mmd_armature(armature):
            warnings.append(t("MMD.validation.not_mmd_model"))
        
        return errors, warnings
    
    @staticmethod
    def _is_rigify_armature(armature: Object) -> bool:
        """Check if armature is Rigify/Metarig"""
        if armature.name.lower() == 'metarig':
            return True
            
        rigify_bones = {'brow.B.L', 'lip.B.R', 'lip.T.R', 'lip.B.L', 'lip.T.L'}
        
        for bone in armature.data.bones:
            if bone.name.startswith(('DEF-', 'MCH-', 'ORG-')) or bone.name in rigify_bones:
                return True
                
        return False
    
    @staticmethod
    def _is_mmd_armature(armature: Object) -> bool:
        """Check if armature appears to be an MMD/PMX model"""
        # Check for MMD parent structure (Empty with mmd_root)
        if armature.parent and armature.parent.type == 'EMPTY':
            if hasattr(armature.parent, 'mmd_root'):
                return True
        
        # Check for common Japanese MMD bone names
        mmd_bone_indicators = [
            '全ての親', 'センター', '上半身', '下半身', '首', '頭',
            '左腕', '右腕', '左足', '右足', '左肩', '右肩',
            '左ひじ', '右ひじ', '左ひざ', '右ひざ',
            '左手首', '右手首', '左足首', '右足首',
            'center', 'upper body', 'lower body', 'groove', 'グルーブ',
        ]
        
        bone_names_lower = [bone.name.lower() for bone in armature.data.bones]
        matches = sum(1 for indicator in mmd_bone_indicators 
                      if any(indicator.lower() in name for name in bone_names_lower))
        
        return matches >= 3
    
    @staticmethod
    def _validate_meshes(context: Context, armature: Object) -> Tuple[List[str], List[str]]:
        """Validate mesh requirements"""
        errors: List[str] = []
        warnings: List[str] = []
        
        meshes = get_meshes_for_armature(armature)
        
        if not meshes:
            warnings.append(t("MMD.validation.no_meshes"))
            return errors, warnings
        
        # Check for valid vertex groups
        for mesh in meshes:
            if not mesh.vertex_groups:
                warnings.append(t("MMD.validation.mesh_no_vertex_groups", mesh=mesh.name))
            
            # Check for multi-user data (shared mesh data)
            if mesh.data.users > 1:
                warnings.append(t("MMD.validation.mesh_multi_user", mesh=mesh.name))
        
        return errors, warnings
    
    @staticmethod
    def check_single_user_meshes(armature: Object) -> List[Object]:
        """
        Check if all meshes are single-user and return list of multi-user meshes.
        
        Returns:
            List of mesh objects that have multi-user data
        """
        multi_user_meshes: List[Object] = []
        meshes = get_meshes_for_armature(armature)
        
        for mesh in meshes:
            if mesh.data.users > 1:
                multi_user_meshes.append(mesh)
        
        return multi_user_meshes


# BONE CACHE SYSTEM

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

# MMD ROOT HANDLER

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

# BONE MORPH CONVERTER (Linux Compatible)

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


class BoneDictionaryBuilder:
    """Build bone dictionaries for renaming and reweighting operations"""
    
    @staticmethod
    def build_rename_dictionary() -> Dict[str, List[str]]:
        """Build complete rename dictionary including fingers"""
        rename_dict = copy.deepcopy(mmd_bone_rename)
        
        # Add finger bones
        for side_bones in mmd_finger_patterns.values():
            for new_name, old_names in side_bones.items():
                rename_dict[new_name] = old_names
        
        return rename_dict
    
    @staticmethod
    def build_reweight_dictionary(rename_dict: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Build reweight dictionary - renamed bones should also be reweighted"""
        reweight_dict = copy.deepcopy(mmd_bone_reweight)
        
        # Add renamed bones to reweight dictionary
        for new_name, old_names in rename_dict.items():
            if new_name not in reweight_dict:
                reweight_dict[new_name] = []
            # Add any old names that aren't already in the reweight list
            for old_name in old_names:
                if old_name not in reweight_dict[new_name]:
                    reweight_dict[new_name].append(old_name)
        
        return reweight_dict
    
    @staticmethod
    def count_processing_steps(rename_dict: Dict[str, List[str]], 
                               reweight_dict: Dict[str, List[str]],
                               armature: Object) -> int:
        """Count total steps for progress bar"""
        steps = 0
        
        # Count rename operations
        for bone_new, bones_old in rename_dict.items():
            for bone_old in bones_old:
                steps += 1
        
        # Count reweight operations
        for bone_new, bones_old in reweight_dict.items():
            for bone_old in bones_old:
                steps += 1
        
        # Add bone count for initial processing
        steps += len(armature.data.bones) if armature.data else 0
        
        return steps

# MAIN FIX ARMATURE OPERATOR

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
        # Basic check - more detailed validation happens in execute
        return armature.type == 'ARMATURE'

    def execute(self, context: Context) -> Set[str]:
        armature = get_active_armature(context)
        toolkit = context.scene.avatar_toolkit
        
        logger.info(f"Starting MMD armature fix for: {armature.name}")
        
        # PHASE 1: Validation & Setup
        
        # Save current state
        saved_data = SavedData()
        
        # Step 2: Validate armature requirements
        errors, warnings = MMDArmatureValidator.validate_armature_requirements(context, armature)
        
        # Report warnings
        for warning in warnings:
            self.report({'WARNING'}, warning)
            logger.warning(warning)
        
        # Check for errors
        if errors:
            for error in errors:
                self.report({'ERROR'}, error)
                logger.error(error)
            return {'CANCELLED'}
        
        # Check for Rigify/VRM
        if MMDArmatureValidator._is_rigify_armature(armature):
            self.report({'ERROR'}, t("MMD.validation.rigify_detected"))
            return {'CANCELLED'}
        
        # nitialize bone cache
        bone_cache = BoneCache(armature)
        logger.debug(f"Bone cache initialized with {len(bone_cache.bone_name_map)} bones")
        
        # Check if MMD model and handle bone collections backup
        mmd_root = MMDRootHandler.get_mmd_root(armature)
        bone_collections_backup: List[Dict[str, Any]] = []
        
        if mmd_root:
            logger.info("MMD model detected")
            bone_collections_backup = MMDRootHandler.backup_bone_collections(armature)
            logger.debug(f"Backed up {len(bone_collections_backup)} bone collections")
        else:
            logger.info("Non-MMD model - some MMD-specific features will be skipped")
        
        # Verify meshes are single-user (show popup if not)
        multi_user_meshes = MMDArmatureValidator.check_single_user_meshes(armature)
        if multi_user_meshes:
            mesh_names = ', '.join([m.name for m in multi_user_meshes])
            self.report({'WARNING'}, t("MMD.validation.multi_user_meshes", meshes=mesh_names))
            logger.warning(f"Multi-user meshes detected: {mesh_names}")
            # Make single user
            for mesh in multi_user_meshes:
                mesh.data = mesh.data.copy()
                logger.debug(f"Made {mesh.name} single-user")
        
        try:
            # Store settings that might break during conversion
            data_breaking = store_breaking_settings_armature(armature)
            
            # PHASE 2: Model Type Detection & Preparation
            
            # Set default stage - unhide all, ensure object mode, set armature active - we need to unhide things because blender needs to see them to process
            unhide_all()
            unselect_all()
            
            # Ensure all objects are in object mode
            for obj in get_objects():
                if obj.mode != 'OBJECT':
                    set_active(obj, skip_sel=True)
                    bpy.ops.object.mode_set(mode='OBJECT')
                    unselect_all()
            
            set_active(armature)
            
            # Prepare bone dictionaries
            rename_dict = BoneDictionaryBuilder.build_rename_dictionary()
            reweight_dict = BoneDictionaryBuilder.build_reweight_dictionary(rename_dict)
            total_steps = BoneDictionaryBuilder.count_processing_steps(rename_dict, reweight_dict, armature)
            
            logger.debug(f"Prepared dictionaries - rename: {len(rename_dict)}, reweight: {len(reweight_dict)}")
            logger.debug(f"Total processing steps: {total_steps}")
            
            # Handle MMD-specific operations
            if mmd_root:
                self._handle_mmd_operations(context, armature, mmd_root, toolkit)
            
            # Handle "Blenda" model quirk
            self._handle_blenda_quirk(armature)
            
            # Remove unused animation data
            self._remove_unused_animations(armature)
            
            # PHASE 3: Scene & Transform Setup
            
            # Remove rigidbodies and joints (if option enabled)
            if toolkit.mmd_remove_rigidbodies:
                removed_rb = self._remove_rigidbodies_and_joints(armature)
                if removed_rb > 0:
                    logger.info(f"Removed {removed_rb} rigidbody/joint objects")
            
            # Handle weird FBX scaling (models scaled to 0.01)
            if toolkit.mmd_fix_fbx_scale:
                self._fix_fbx_scaling(context, armature)
            
            # Fix zero-length bones (prevents bones from disappearing)
            fix_zero_length_bones(armature)
            logger.debug("Fixed zero-length bones")
            
            # Apply transforms on armature and meshes
            if toolkit.mmd_apply_transforms:
                set_active(armature)
                bpy.ops.avatar_toolkit.apply_transforms()
                logger.debug("Applied transforms using ATK operator")
            
            # Join child meshes if option enabled and multiple children exist
            if toolkit.mmd_join_meshes:
                self._join_child_meshes(context, armature)
            
            # Unlock all transforms on armature and bones
            self._unlock_all_transforms(armature)
            
            # Remove empty MMD object and unused objects
            if toolkit.mmd_remove_empty_objects:
                self._remove_empty_and_unused(context, armature)
            
            # PHASE 4: Mesh Processing
            
            # Get meshes for processing
            meshes = get_meshes_for_armature(armature)
            
            if meshes:
                logger.info(f"Processing {len(meshes)} mesh(es)")
                
                for mesh in meshes:
                    logger.debug(f"Processing mesh: {mesh.name}")
                    
                    # Remove duplicate armature modifiers
                    self._remove_duplicate_armature_modifiers(mesh, armature)
                    
                    # Add armature modifier if missing (uses ATK add_armature_modifier)
                    self._ensure_armature_modifier(mesh, armature)
                    
                    # Clean shape keys (remove unused) - uses ATK clean_shapekeys
                    if toolkit.mmd_clean_shapekeys:
                        self._clean_mesh_shapekeys(mesh)
                    
                    # Set parent to armature (ensure proper parenting)
                    self._ensure_mesh_parenting(mesh, armature)
                    
                    # Fix material names (translate Japanese names)
                    if toolkit.mmd_translate_materials:
                        self._fix_material_names(mesh)
                
                # Remove doubles using ATK operator (handles all meshes + shapekeys safely)
                if toolkit.mmd_remove_doubles:
                    try:
                        # Set armature as active for the operator
                        set_active(armature)
                        bpy.ops.avatar_toolkit.remove_doubles('INVOKE_DEFAULT', merge_distance=0.0001)
                        logger.info("Invoked ATK remove doubles operator")
                    except Exception as e:
                        logger.warning(f"Could not invoke remove doubles operator: {e}")
            else:
                logger.warning("No meshes found for armature")
            
            # Store dictionaries for Phase 5
            context.scene['_mmd_fixer_rename_dict'] = str(rename_dict)
            context.scene['_mmd_fixer_reweight_dict'] = str(reweight_dict)
            
            # Restore settings
            restore_breaking_settings_armature(armature, data_breaking)
            
            # Clean up bone cache
            bone_cache.clear_cache()
            
            self.report({'INFO'}, t("MMD.fix_armature.phase_complete_4"))
            logger.info("MMD armature fix Phase 1-4 completed successfully")
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
        
        # Disable toon and sphere texture if available
        try:
            if hasattr(mmd_root, 'use_toon_texture'):
                mmd_root.use_toon_texture = False
            if hasattr(mmd_root, 'use_sphere_texture'):
                mmd_root.use_sphere_texture = False
        except Exception as e:
            logger.debug(f"Could not disable toon/sphere textures: {e}")
        
        # Convert bone morphs to shape keys (Linux compatible)
        if hasattr(mmd_root, 'bone_morphs') and len(mmd_root.bone_morphs) > 0:
            logger.info(f"Converting {len(mmd_root.bone_morphs)} bone morphs to shape keys")
            
            # Try using built-in mmd_tools operators first, fall back to native
            try:
                # Use built-in mmd_tools morph conversion operator
                bpy.ops.mmd_tools.convert_bone_morph_to_vertex_morph()
                logger.info("Converted bone morphs using mmd_tools operator")
            except Exception as e:
                # Fall back to native conversion
                logger.debug(f"mmd_tools operator not available: {e}")
                converted = BoneMorphConverter.convert_bone_morphs_to_shapekeys(
                    context, armature, mmd_root
                )
                logger.info(f"Converted {converted} bone morphs using native method")
        
        # Translate bone names from Japanese to English (if enabled)
        if toolkit.mmd_translate_names and toolkit.mmd_translate_bones:
            translated = self._translate_bone_names(armature)
            logger.info(f"Translated {translated} bone names")
        
        # Translate shape key names from Japanese to English (if enabled)
        if toolkit.mmd_translate_names and toolkit.mmd_translate_shapekeys:
            translated = self._translate_shapekey_names(armature)
            logger.info(f"Translated {translated} shape key names")
        
        # Translate object names (meshes, etc.) from Japanese to English (if enabled)
        if toolkit.mmd_translate_names and toolkit.mmd_translate_objects:
            translated = self._translate_object_names(armature)
            logger.info(f"Translated {translated} object names")
        
        # Clean up MMD-specific data
        self._cleanup_mmd_data(context, armature, mmd_root)
        
        # Remove bone collections to prevent crashes
        removed_collections = MMDRootHandler.remove_bone_collections(armature)
        if removed_collections > 0:
            logger.debug(f"Removed {removed_collections} bone collections")

    def _handle_blenda_quirk(self, armature: Object) -> None:
        """
        Handle "Blenda" model quirk where Spine1 represents hips.
        This conflicts with other mappings, so we rename it.
        """
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
            
            # Rename the bone
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

    # PHASE 2 METHODS: Translation & MMD Cleanup

    def _translate_bone_names(self, armature: Object) -> int:
        """Translate bone names from Japanese to English.
        Also updates vertex groups in all meshes."""
        translated_count = 0
        bone_rename_map: Dict[str, str] = {}
        
        # First pass: collect renames (can't rename while iterating)
        for bone in armature.data.bones:
            original_name = bone.name
            if self._contains_japanese(original_name):
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
                    final_name = self._get_unique_bone_name(armature, new_name, old_name)
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

    def _translate_shapekey_names(self, armature: Object) -> int:
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
                if self._contains_japanese(original_name):

                    new_name = original_name
                    for half, full in jp_half_to_full_tuples:
                        new_name = new_name.replace(half, full)
                    
                    new_name = translateFromJp(new_name)
                    
                    if new_name != original_name:
                        key_block.name = new_name
                        translated_count += 1
                        logger.debug(f"Translated shape key: {original_name} -> {new_name}")
        
        return translated_count

    def _translate_object_names(self, armature: Object) -> int:
        """Translate object names (meshes, etc.) from Japanese to English."""
        translated_count = 0
        
        # Translate armature name
        if self._contains_japanese(armature.name):
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
            if self._contains_japanese(mesh.name):
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
            if self._contains_japanese(empty.name):
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

    def _cleanup_mmd_data(self, context: Context, armature: Object, mmd_root: Any) -> None:
        """Clean up MMD-specific data that may cause issues."""
        logger.debug("Cleaning up MMD-specific data")
        
        # Clear MMD bone order if present
        if hasattr(mmd_root, 'bone_order'):
            try:
                mmd_root.bone_order.clear()
                logger.debug("Cleared MMD bone order")
            except Exception as e:
                logger.debug(f"Could not clear bone order: {e}")
        
        # Clear display item frames if present (after processing)
        # Note: We keep these for now as they might be useful
        
        # Clear UV morphs data type vertex groups
        if hasattr(mmd_root, 'uv_morphs'):
            for uv_morph in mmd_root.uv_morphs:
                if hasattr(uv_morph, 'data_type') and uv_morph.data_type == 'VERTEX_GROUP':
                    # Clean up UV morph vertex groups from meshes
                    meshes = get_meshes_for_armature(armature)
                    for mesh in meshes:
                        # Remove UV morph vertex groups (they start with UV_)
                        vg_to_remove = [vg.name for vg in mesh.vertex_groups 
                                       if vg.name.startswith(f"UV_{uv_morph.name}")]
                        for vg_name in vg_to_remove:
                            mesh.vertex_groups.remove(mesh.vertex_groups[vg_name])
        
        # Disable IK on pose bones (they'll be removed later but disable first)
        for bone in armature.pose.bones:
            for constraint in bone.constraints:
                if constraint.type == 'IK':
                    constraint.mute = True
        
        logger.debug("MMD data cleanup complete")

    def _get_unique_bone_name(self, armature: Object, base_name: str, 
                              current_name: str) -> str:
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

    # PHASE 3 METHODS: Scene & Transform Setup

    def _remove_rigidbodies_and_joints(self, armature: Object) -> int:
        """Remove rigidbodies and joints associated with an armature.
        Similar to delete_rigidbodies_and_joints in armature_merging.py"""
        removed_count = 0
        to_delete: List[Object] = []
        
        # Find the top-level parent
        parent: Object = armature
        while parent.parent:
            parent = parent.parent
        
        # Search for rigidbody/joint objects in children
        def find_physics_objects(obj: Object) -> None:
            name_lower = obj.name.lower()
            if 'rigidbodies' in name_lower or 'joints' in name_lower or \
               'rigidbody' in name_lower or 'joint' in name_lower or \
               '剛体' in obj.name or 'Joint' in obj.name:
                to_delete.append(obj)
            for child in obj.children:
                find_physics_objects(child)
        
        find_physics_objects(parent)
        
        # Also check direct children of the armature
        for child in armature.children:
            name_lower = child.name.lower()
            if 'rigidbodies' in name_lower or 'joints' in name_lower or \
               'rigidbody' in name_lower or 'joint' in name_lower:
                if child not in to_delete:
                    to_delete.append(child)
        
        # Delete found objects
        for obj in to_delete:
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
                removed_count += 1
            except Exception as e:
                logger.warning(f"Could not remove physics object {obj.name}: {e}")
        
        return removed_count

    def _fix_fbx_scaling(self, context: Context, armature: Object) -> None:
        """Handle weird FBX scaling where models are scaled to 0.01.
        This is common with some FBX exporters."""
        scale_threshold = 0.015
        
        # Check if armature has the problematic 0.01 scale
        if (round(armature.scale[0], 2) == 0.01 and
            round(armature.scale[1], 2) == 0.01 and
            round(armature.scale[2], 2) == 0.01):
            
            logger.info("Detected FBX 0.01 scaling - fixing transforms")
            
            # Scale up the armature
            armature.scale = (1.0, 1.0, 1.0)
            
            # Apply scale to meshes too
            meshes = get_meshes_for_armature(armature)
            for mesh in meshes:
                if (round(mesh.scale[0], 2) == 0.01 and
                    round(mesh.scale[1], 2) == 0.01 and
                    round(mesh.scale[2], 2) == 0.01):
                    mesh.scale = (1.0, 1.0, 1.0)

    def _join_child_meshes(self, context: Context, armature: Object) -> None:
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

    def _unlock_all_transforms(self, armature: Object) -> None:
        """Unlock all transforms on armature and its bones."""
        # Unlock armature transforms
        for i in range(3):
            armature.lock_location[i] = False
            armature.lock_rotation[i] = False
            armature.lock_scale[i] = False
        
        # Unlock all bone transforms
        for bone in armature.pose.bones:
            for i in range(3):
                bone.lock_location[i] = False
                bone.lock_rotation[i] = False
                bone.lock_scale[i] = False
            
            # Also unlock rotation_w for quaternion rotation
            if hasattr(bone, 'lock_rotation_w'):
                bone.lock_rotation_w = False
            
            # Unlock IK settings if present
            if hasattr(bone, 'lock_ik_x'):
                bone.lock_ik_x = False
                bone.lock_ik_y = False
                bone.lock_ik_z = False
        
        logger.debug("Unlocked all transforms on armature and bones")

    def _remove_empty_and_unused(self, context: Context, armature: Object) -> None:
        """Remove empty MMD object and other unused objects."""
        removed_count = 0
        
        # Check if armature has an empty parent 
        if armature.parent and armature.parent.type == 'EMPTY':
            empty_parent = armature.parent
            
            # Check if this is an MMD root empty
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
                
                # Remove the empty
                try:
                    bpy.data.objects.remove(empty_parent, do_unlink=True)
                    removed_count += 1
                    logger.info("Removed MMD parent empty object")
                except Exception as e:
                    logger.warning(f"Could not remove MMD empty: {e}")
        
        self._remove_default_objects()
        
        # Clean up unused data blocks
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
            # Check base name without .001 etc suffix
            base_name = obj.name.split('.')[0]
            if base_name in default_names:
                # Only remove if it's actually a default object
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

    # PHASE 4 METHODS: Mesh Processing

    def _remove_duplicate_armature_modifiers(self, mesh: Object, armature: Object) -> int:
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

    def _ensure_armature_modifier(self, mesh: Object, armature: Object) -> bool:
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

    def _clean_mesh_shapekeys(self, mesh: Object) -> int:
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

    def _ensure_mesh_parenting(self, mesh: Object, armature: Object) -> None:
        """Ensure mesh is properly parented to the armature."""
        if mesh.parent != armature:

            matrix_world = mesh.matrix_world.copy()
            
            # Set parent
            mesh.parent = armature
            mesh.parent_type = 'OBJECT'
            
            # Restore world position
            mesh.matrix_world = matrix_world
            
            logger.debug(f"Re-parented {mesh.name} to {armature.name}")

    def _fix_material_names(self, mesh: Object) -> int:
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
            if self._contains_japanese(original_name):
                new_name = self._translate_material_name(original_name)
                
                if new_name != original_name:
                    # Ensure unique name
                    new_name = self._get_unique_material_name(new_name)
                    mat.name = new_name
                    renamed_count += 1
                    logger.debug(f"Renamed material: {original_name} -> {new_name}")
        
        if renamed_count > 0:
            logger.info(f"Renamed {renamed_count} materials in {mesh.name}")
        
        return renamed_count

    def _contains_japanese(self, text: str) -> bool:
        """Check if text contains Japanese characters"""
        for char in text:
            # Hiragana, Katakana, CJK Unified Ideographs
            if ('\u3040' <= char <= '\u309F' or  # Hiragana
                '\u30A0' <= char <= '\u30FF' or  # Katakana
                '\u4E00' <= char <= '\u9FFF' or  # CJK
                '\uFF00' <= char <= '\uFFEF'):   # Full-width
                return True
        return False

    def _translate_material_name(self, name: str) -> str:
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

    def _get_unique_material_name(self, base_name: str) -> str:
        """Get a unique material name"""
        if base_name not in bpy.data.materials:
            return base_name
        
        counter = 1
        while f"{base_name}.{counter:03d}" in bpy.data.materials:
            counter += 1
        
        return f"{base_name}.{counter:03d}"


# HELPER FUNCTIONS

def detect_mmd_armature(armature: Object) -> bool:
    """Public function to detect if armature is MMD model"""
    return MMDArmatureValidator._is_mmd_armature(armature)


def get_mmd_root(armature: Object) -> Optional[Any]:
    """Public function to get MMD root"""
    return MMDRootHandler.get_mmd_root(armature)
