# GPL License
# Avatar Toolkit MMD Converter - Dictionary Builder Module

import copy
from typing import Dict, List
from bpy.types import Object

from ....core.enhanced_dictionaries import (
    mmd_bone_rename,
    mmd_bone_reweight,
    mmd_finger_patterns,
)


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
