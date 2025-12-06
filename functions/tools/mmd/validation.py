# GPL License
# Avatar Toolkit MMD Converter - Validation Module

from typing import List, Tuple, Optional
from bpy.types import Context, Object

from ....core.logging_setup import logger
from ....core.translations import t
from ....core.common import get_meshes_for_armature


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


def detect_mmd_armature(armature: Object) -> bool:
    """Public function to detect if armature is MMD model"""
    return MMDArmatureValidator._is_mmd_armature(armature)
