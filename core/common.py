import bpy
import numpy as np
import threading
import time
import webbrowser
import typing
import struct
from io import BytesIO
import numpy.typing as npt

from typing import Optional, Tuple, List, Set, Dict, Any, Generator, Callable, Union, Type
from mathutils import Vector, Matrix
from bpy.types import (Context, Object, Modifier, EditBone, Operator, 
                      VertexGroup, ShapeKey, Bone, Mesh, Armature, PropertyGroup)
from functools import lru_cache
from bpy.props import PointerProperty, IntProperty, StringProperty
from bpy.utils import register_class
from ..core.logging_setup import logger
from ..core.translations import t
from ..core.dictionaries import bone_names

class ProgressTracker:
    """Universal progress tracking for Avatar Toolkit operations"""
    
    def __init__(self, context: Context, total_steps: int, operation_name: str = "Operation") -> None:
        self.context: Context = context
        self.total: int = total_steps
        self.current: int = 0
        self.operation_name: str = operation_name
        self.wm = context.window_manager
        
    def step(self, message: str = "") -> None:
        """Update progress by one step"""
        self.current += 1
        progress = self.current / self.total
        self.wm.progress_begin(0, 100)
        self.wm.progress_update(progress * 100)
        logger.debug(f"{self.operation_name} - {progress:.1%}: {message}")
        
    def __enter__(self) -> 'ProgressTracker':
        logger.info(f"Starting {self.operation_name}")
        return self
        
    def __exit__(self, exc_type: Optional[Type[BaseException]], 
                 exc_val: Optional[BaseException], 
                 exc_tb: Optional[Any]) -> None:
        self.wm.progress_end()
        logger.info(f"Completed {self.operation_name}")

def get_active_armature(context: Context) -> Optional[Object]:
    """Get the currently selected armature from Avatar Toolkit properties"""
    armature_name = str(context.scene.avatar_toolkit.active_armature)
    if armature_name and armature_name != 'NONE':
        return bpy.data.objects.get(armature_name)
    return None

def set_active_armature(context: Context, armature: Object) -> None:
    """Set the active armature for Avatar Toolkit operations"""
    context.scene.avatar_toolkit.active_armature = armature

def get_armature_list(self: Optional[Any] = None, context: Optional[Context] = None) -> List[Tuple[str, str, str]]:
    """Get list of all armature objects in the scene"""
    if context is None:
        context = bpy.context
    armatures = [(obj.name, obj.name, "") for obj in context.scene.objects if obj.type == 'ARMATURE']
    if not armatures:
        return [('NONE', t("Armature.validation.no_armature"), '')]
    return armatures

def validate_armature(armature: Object) -> Tuple[bool, List[str]]:
    """Enhanced armature validation with multiple validation modes"""
    validation_mode = bpy.context.scene.avatar_toolkit.validation_mode
    messages: List[str] = []
    
    if validation_mode == 'NONE':
        return True, []
        
    if not armature or armature.type != 'ARMATURE' or not armature.data.bones:
        return False, [t("Armature.validation.basic_check_failed")]
        
    found_bones: Dict[str, Bone] = {bone.name.lower(): bone for bone in armature.data.bones}
    essential_bones: Set[str] = {'hips', 'spine', 'chest', 'neck', 'head'}
    
    missing_bones: List[str] = []
    for bone in essential_bones:
        if not any(alt_name in found_bones for alt_name in bone_names[bone]):
            missing_bones.append(bone)
    
    if missing_bones:
        messages.append(t("Armature.validation.missing_bones", bones=", ".join(missing_bones)))
    
    if validation_mode == 'STRICT':
        hierarchy: List[Tuple[str, str]] = [
            ('hips', 'spine'), ('spine', 'chest'), 
            ('chest', 'neck'), ('neck', 'head')
        ]
        for parent, child in hierarchy:
            if not validate_bone_hierarchy(found_bones, parent, child):
                messages.append(t("Armature.validation.invalid_hierarchy", 
                                parent=parent, child=child))
        
        symmetry_pairs: List[Tuple[str, str, str]] = [('arm', 'l', 'r'), ('leg', 'l', 'r')]
        for base, left, right in symmetry_pairs:
            if not validate_symmetry(found_bones, base, left, right):
                messages.append(t("Armature.validation.asymmetric_bones", bone=base))
                
        if (not validate_symmetry(found_bones, 'hand', 'l', 'r') and 
            not validate_symmetry(found_bones, 'wrist', 'l', 'r')):
            messages.append(t("Armature.validation.asymmetric_hand_wrist"))
    
    is_valid: bool = len(messages) == 0
    return is_valid, messages

def validate_bone_hierarchy(bones: Dict[str, Bone], parent_name: str, child_name: str) -> bool:
    """Validate if there is a valid parent-child relationship between bones"""
    parent_bone: Optional[Bone] = None
    child_bone: Optional[Bone] = None
    
    for alt_name in bone_names[parent_name]:
        if alt_name in bones:
            parent_bone = bones[alt_name]
            break
            
    for alt_name in bone_names[child_name]:
        if alt_name in bones:
            child_bone = bones[alt_name]
            break
    
    if not parent_bone or not child_bone:
        return False
        
    return child_bone.parent == parent_bone

def validate_symmetry(bones: Dict[str, Bone], base: str, left: str, right: str) -> bool:
    """Validate if matching left and right bones exist for a given base bone name"""
    left_patterns: List[str] = [
        f"{base}.{left}",
        f"{base}_{left}",
        f"{left}_{base}"
    ]
    
    right_patterns: List[str] = [
        f"{base}.{right}",
        f"{base}_{right}", 
        f"{right}_{base}"
    ]
    
    left_exists: bool = any(pattern in bones for pattern in left_patterns)
    right_exists: bool = any(pattern in bones for pattern in right_patterns)
    
    return left_exists and right_exists
  
def auto_select_single_armature(context: Context) -> None:
    """Automatically select armature if only one exists in scene"""
    armatures: List[Tuple[str, str, str]] = get_armature_list(context)
    if len(armatures) == 1 and armatures[0][0] != 'NONE':
        toolkit = context.scene.avatar_toolkit
        set_active_armature(context, armatures[0])

def clear_default_objects() -> None:
    """Removes default Blender objects"""
    default_names: Set[str] = {'Cube', 'Light', 'Camera'}
    for obj in bpy.data.objects:
        if obj.name.split('.')[0] in default_names:
            bpy.data.objects.remove(obj, do_unlink=True)

def get_armature_stats(armature: Object) -> Dict[str, Union[int, bool, str]]:
    """Get statistics about the armature"""
    return {
        'bone_count': len(armature.data.bones),
        'has_pose': bool(armature.pose),
        'visible': not armature.hide_viewport,
        'name': armature.name
    }

def get_all_meshes(context: Context) -> List[Object]:
    """Get all mesh objects parented to the active armature"""
    armature: Optional[Object] = get_active_armature(context)
    if armature:
        return [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj.parent == armature]
    return []

def validate_mesh_for_pose(mesh_obj: Object) -> Tuple[bool, str]:
    """Validate mesh object for pose operations"""
    if not mesh_obj.data:
        return False, t("Mesh.validation.no_data")
        
    if not mesh_obj.vertex_groups:
        return False, t("Mesh.validation.no_vertex_groups")
        
    armature_mods: List[Modifier] = [mod for mod in mesh_obj.modifiers if mod.type == 'ARMATURE']
    if not armature_mods:
        return False, t("Mesh.validation.no_armature_modifier")
    
    return True, t("Mesh.validation.valid")

def cache_vertex_positions(mesh_obj: Object) -> npt.NDArray[np.float32]:
    """Cache vertex positions for a mesh object"""
    vertices = mesh_obj.data.vertices
    positions: npt.NDArray[np.float32] = np.empty(len(vertices) * 3, dtype=np.float32)
    vertices.foreach_get('co', positions)
    return positions.reshape(-1, 3)

def apply_vertex_positions(vertices: Object, positions: npt.NDArray[np.float32]) -> None:
    """Apply cached vertex positions to mesh in batch"""
    vertices.foreach_set('co', positions.flatten())

def process_armature_modifiers(mesh_obj: Object) -> List[Dict[str, Any]]:
    """Process and store armature modifier states"""
    modifier_states: List[Dict[str, Any]] = []
    for mod in mesh_obj.modifiers:
        if mod.type == 'ARMATURE':
            modifier_states.append({
                'name': mod.name,
                'object': mod.object,
                'vertex_group': mod.vertex_group,
                'show_viewport': mod.show_viewport
            })
    return modifier_states

def apply_pose_as_rest(context: Context, armature_obj: Object, meshes: List[Object]) -> Tuple[bool, str]:
    """Apply current pose as rest pose for armature and update meshes"""
    try:
        logger.info(f"Starting pose application for {len(meshes)} meshes")
        
        with ProgressTracker(context, len(meshes), "Applying Pose") as progress:
            for mesh_obj in meshes:
                if not mesh_obj.data:
                    continue
                    
                if mesh_obj.data.shape_keys and mesh_obj.data.shape_keys.key_blocks:
                    apply_armature_to_mesh_with_shapekeys(armature_obj, mesh_obj, context)
                else:
                    apply_armature_to_mesh(armature_obj, mesh_obj)
                
                progress.step(f"Processed {mesh_obj.name}")
            
            bpy.ops.object.mode_set(mode='POSE')
            bpy.ops.pose.armature_apply(selected=False)
            bpy.ops.object.mode_set(mode='OBJECT')
            
            return True, t("Operation.pose_applied")
            
    except Exception as e:
        logger.error(f"Error applying pose as rest: {str(e)}")
        return False, str(e)
    
def apply_armature_to_mesh(armature_obj: Object, mesh_obj: Object) -> None:
    """Apply armature deformation to mesh"""
    armature_mod: Modifier = mesh_obj.modifiers.new('PoseToRest', 'ARMATURE')
    armature_mod.object = armature_obj
    
    if bpy.app.version >= (3, 5):
        mesh_obj.modifiers.move(mesh_obj.modifiers.find(armature_mod.name), 0)
    else:
        for _ in range(len(mesh_obj.modifiers) - 1):
            bpy.ops.object.modifier_move_up(modifier=armature_mod.name)
            
    with bpy.context.temp_override(object=mesh_obj):
        bpy.ops.object.modifier_apply(modifier=armature_mod.name)

def apply_armature_to_mesh_with_shapekeys(armature_obj: Object, mesh_obj: Object, context: Context) -> None:
    """Apply armature deformation to mesh with shape keys"""
    old_active_index: int = mesh_obj.active_shape_key_index
    old_show_only: bool = mesh_obj.show_only_shape_key
    mesh_obj.show_only_shape_key = True
    
    shape_keys: List[ShapeKey] = mesh_obj.data.shape_keys.key_blocks
    vertex_groups: List[str] = []
    mutes: List[bool] = []
    
    for sk in shape_keys:
        vertex_groups.append(sk.vertex_group)
        sk.vertex_group = ''
        mutes.append(sk.mute)
        sk.mute = False

    disabled_mods: List[Modifier] = []
    for mod in mesh_obj.modifiers:
        if mod.show_viewport:
            mod.show_viewport = False
            disabled_mods.append(mod)

    arm_mod: Modifier = mesh_obj.modifiers.new('PoseToRest', 'ARMATURE')
    arm_mod.object = armature_obj
    
    co_length: int = len(mesh_obj.data.vertices) * 3
    eval_cos: npt.NDArray[np.float32] = np.empty(co_length, dtype=np.single)
    
    for i, shape_key in enumerate(shape_keys):
        mesh_obj.active_shape_key_index = i
        
        depsgraph = context.evaluated_depsgraph_get()
        eval_mesh = mesh_obj.evaluated_get(depsgraph)
        eval_mesh.data.vertices.foreach_get('co', eval_cos)
        
        shape_key.data.foreach_set('co', eval_cos)
        if i == 0:
            mesh_obj.data.vertices.foreach_set('co', eval_cos)

    for mod in disabled_mods:
        mod.show_viewport = True
        
    mesh_obj.modifiers.remove(arm_mod)
    
    for sk, vg, mute in zip(shape_keys, vertex_groups, mutes):
        sk.vertex_group = vg
        sk.mute = mute
        
    mesh_obj.active_shape_key_index = old_active_index
    mesh_obj.show_only_shape_key = old_show_only

def validate_meshes(meshes: List[Object]) -> Tuple[bool, str]:
    """Validates a list of mesh objects to ensure they are suitable for joining operations"""
    if not meshes:
        return False, t("Optimization.no_meshes")
    if not all(mesh.data for mesh in meshes):
        return False, t("Optimization.invalid_mesh_data")
    if not all(mesh.type == 'MESH' for mesh in meshes):
        return False, t("Optimization.non_mesh_objects")
    return True, ""

def join_mesh_objects(context: Context, meshes: List[Object], progress: Optional[ProgressTracker] = None) -> Optional[Object]:
    """Combines multiple mesh objects into a single mesh with proper cleanup and UV fixing"""
    try:
        # Store UV maps before joining
        uv_maps_data = {}
        for mesh in meshes:
            uv_maps_data[mesh.name] = {uv.name: uv.data.copy() for uv in mesh.data.uv_layers}

        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        
        for mesh in meshes:
            mesh.select_set(True)
        
        if context.selected_objects:
            context.view_layer.objects.active = context.selected_objects[0]
            
            if progress:
                progress.step(t("Optimization.joining_meshes"))
            bpy.ops.object.join()
            
            if progress:
                progress.step(t("Optimization.applying_transforms"))
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            
            if progress:
                progress.step(t("Optimization.fixing_uvs"))
            fix_uv_coordinates(context)
            
            # Restore UV maps after joining
            joined_mesh = context.active_object
            for uv_name, uv_data in uv_maps_data.items():
                for map_name, map_data in uv_data.items():
                    if map_name not in joined_mesh.data.uv_layers:
                        joined_mesh.data.uv_layers.new(name=map_name)
                    joined_mesh.data.uv_layers[map_name].data.foreach_set("uv", map_data)
            
            return context.active_object 
            
        return None
            
    except Exception as e:
        logger.error(f"Failed to join meshes: {str(e)}")
        return None

def fix_uv_coordinates(context: Context) -> None:
    """Normalizes and fixes UV coordinates for the active mesh object"""
    obj: Object = context.object
    current_mode: str = context.mode
    current_active: Object = context.view_layer.objects.active
    current_selected: List[Object] = context.selected_objects.copy()

    try:
        bpy.ops.object.mode_set(mode='OBJECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj
        
        # Process each UV layer
        for uv_layer in obj.data.uv_layers:
            obj.data.uv_layers.active = uv_layer
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            
            with context.temp_override(active_object=obj):
                bpy.ops.uv.select_all(action='SELECT')
                bpy.ops.uv.pack_islands(margin=0.001)
                bpy.ops.uv.average_islands_scale()
            
        logger.debug(f"UV Fix - Successfully processed {obj.name}")

    except Exception as e:
        logger.warning(f"UV Fix - Skipped processing for {obj.name}: {str(e)}")

    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
        for sel_obj in current_selected:
            sel_obj.select_set(True)
        context.view_layer.objects.active = current_active

def clear_unused_data_blocks() -> int:
    """Removes all unused data blocks from the current Blender file"""
    initial_count: int = sum(len(getattr(bpy.data, attr)) for attr in dir(bpy.data)
                        if isinstance(getattr(bpy.data, attr), bpy.types.bpy_prop_collection))
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    final_count: int = sum(len(getattr(bpy.data, attr)) for attr in dir(bpy.data)
                      if isinstance(getattr(bpy.data, attr), bpy.types.bpy_prop_collection))
    return initial_count - final_count

def simplify_bonename(name: str) -> str:
    """Simplify bone name by removing spaces, underscores, dots and converting to lowercase"""
    return name.lower().translate(dict.fromkeys(map(ord, u" _.")))

def duplicate_bone_chain(bones: List[EditBone]) -> List[EditBone]:
    """Duplicate a chain of bones while preserving hierarchy"""
    new_bones: List[EditBone] = []
    parent_map: Dict[EditBone, EditBone] = {}
    
    for bone in bones:
        new_bone = duplicate_bone(bone)
        if bone.parent and bone.parent in parent_map:
            new_bone.parent = parent_map[bone.parent]
        parent_map[bone] = new_bone
        new_bones.append(new_bone)
        
    return new_bones

def restore_bone_transforms(bone: EditBone, transforms: Dict[str, Any]) -> None:
    """Restore bone transforms from stored data"""
    bone.head = transforms['head']
    bone.tail = transforms['tail'] 
    bone.roll = transforms['roll']
    bone.matrix = transforms['matrix']

def get_vertex_weights(mesh_obj: Object, group_name: str) -> Dict[int, float]:
    """Get vertex weights for a specific vertex group"""
    weights: Dict[int, float] = {}
    group_index: int = mesh_obj.vertex_groups[group_name].index
    for vertex in mesh_obj.data.vertices:
        for group in vertex.groups:
            if group.group == group_index:
                weights[vertex.index] = group.weight
    return weights

def transfer_vertex_weights(mesh_obj: Object, source_name: str, target_name: str, threshold: float = 0.01) -> None:
    """Transfer vertex weights from source to target group"""
    if source_name not in mesh_obj.vertex_groups:
        return
        
    source_group: VertexGroup = mesh_obj.vertex_groups[source_name]
    target_group: Optional[VertexGroup] = mesh_obj.vertex_groups.get(target_name)
    
    if not target_group:
        target_group = mesh_obj.vertex_groups.new(name=target_name)
    
    weights: Dict[int, float] = get_vertex_weights(mesh_obj, source_name)
    
    for vertex_index, weight in weights.items():
        if weight > threshold:
            target_group.add([vertex_index], weight, 'ADD')
            
    mesh_obj.vertex_groups.remove(source_group)

def remove_unused_shapekeys(mesh_obj: Object, tolerance: float = 0.001) -> int:
    """Remove unused shape keys from a mesh object"""
    if not mesh_obj.data.shape_keys:
        return 0
        
    key_blocks: List[ShapeKey] = mesh_obj.data.shape_keys.key_blocks
    vertex_count: int = len(mesh_obj.data.vertices)
    removed_count: int = 0
    
    cache: Dict[str, npt.NDArray[np.float32]] = {}
    locations: npt.NDArray[np.float32] = np.empty(3 * vertex_count, dtype=np.float32)
    to_delete: List[str] = []
    
    for key in key_blocks:
        if key == key.relative_key:
            continue
            
        key.data.foreach_get("co", locations)
        
        if key.relative_key.name not in cache:
            rel_locations: npt.NDArray[np.float32] = np.empty(3 * vertex_count, dtype=np.float32)
            key.relative_key.data.foreach_get("co", rel_locations)
            cache[key.relative_key.name] = rel_locations
            
        locations -= cache[key.relative_key.name]
        if (np.abs(locations) < tolerance).all():
            if not any(c in key.name for c in "-=~"):
                to_delete.append(key.name)
                
    for key_name in to_delete:
        mesh_obj.shape_key_remove(key_blocks[key_name])
        removed_count += 1
        
    return removed_count

def has_shapekeys(mesh_obj: Object) -> bool:
    """Check if mesh object has shape keys"""
    return mesh_obj.data.shape_keys is not None

def fix_zero_length_bones(armature: Object) -> None:
    """Fix zero length bones by setting a minimum length"""
    if not armature:
        return
        
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in armature.data.edit_bones:
        if bone.length < 0.001:
            bone.length = 0.001
    bpy.ops.object.mode_set(mode='OBJECT')

def calculate_bone_orientation(mesh: Object, vertices: List[Any]) -> Tuple[Vector, float]:
    """Calculate optimal bone orientation based on mesh geometry"""
    if not vertices:
        return Vector((0, 0, 0.1)), 0.0
        
    coords: List[Vector] = [mesh.data.vertices[v.index].co for v in vertices]
    min_co: Vector = Vector(map(min, zip(*coords)))
    max_co: Vector = Vector(map(max, zip(*coords)))
    dimensions: Vector = max_co - min_co
    
    roll_angle: float = 0.0
    
    return dimensions, roll_angle

def add_armature_modifier(mesh: Object, armature: Object) -> None:
    """Add armature modifier to mesh"""
    for mod in mesh.modifiers:
        if mod.type == 'ARMATURE':
            mesh.modifiers.remove(mod)

    modifier: Modifier = mesh.modifiers.new('Armature', 'ARMATURE')
    modifier.object = armature

def get_shapekeys(context: Context, 
                  names: List[str], 
                  is_mouth: bool, 
                  no_basis: bool, 
                  return_list: bool) -> Union[List[Tuple[str, str, str]], List[str]]:
    """Get shape keys based on specified criteria"""
    choices: List[Tuple[str, str, str]] = []
    choices_simple: List[str] = []
    meshes_list: List[Object] = get_meshes_objects(check=False)

    if meshes_list:
        if is_mouth:
            meshes = [get_objects().get(context.scene.mesh_name_viseme)]
        else:
            meshes = [get_objects().get(context.scene.mesh_name_eye)]
    else:
        return choices

    for mesh in meshes:
        if not mesh or not has_shapekeys(mesh):
            return choices

        for shapekey in mesh.data.shape_keys.key_blocks:
            name = shapekey.name
            if name in choices_simple:
                continue
            if no_basis and name == 'Basis':
                continue
            choices.append((name, name, name))
            choices_simple.append(name)

    _sort_enum_choices_by_identifier_lower(choices)

    choices2: List[Tuple[str, str, str]] = []
    for name in names:
        if name in choices_simple and len(choices) > 1 and choices[0][0] != name:
            continue
        choices2.append((name, name, name))

    choices2.extend(choices)

    if return_list:
        shape_list: List[str] = []
        for choice in choices2:
            shape_list.append(choice[0])
        return shape_list

    return choices2

def _sort_enum_choices_by_identifier_lower(choices: List[Tuple[str, str, str]], in_place: bool = True) -> List[Tuple[str, str, str]]:
    """Sort a list of enum choices by the lowercase of their identifier"""
    def identifier_lower(choice: Tuple[str, str, str]) -> str:
        return choice[0].lower()

    if in_place:
        choices.sort(key=identifier_lower)
    else:
        choices = sorted(choices, key=identifier_lower)
    return choices

def is_enum_empty(string: str) -> bool:
    """Returns True only if the tested string is the empty enum identifier"""
    return _empty_enum_identifier == string

def is_enum_non_empty(string: str) -> bool:
    """Returns False only if the tested string is not the empty enum identifier"""
    return _empty_enum_identifier != string

_empty_enum_identifier: str = 'Cats_empty_enum_identifier'

def get_meshes_objects(check: bool = True) -> List[Object]:
    """Get all mesh objects in the scene"""
    meshes: List[Object] = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    if check and not meshes:
        return []
    return meshes

def get_objects() -> bpy.types.BlendData:
    """Get all objects in the current Blender scene"""
    return bpy.data.objects

def duplicate_bone(bone: EditBone) -> EditBone:
    """Create a duplicate of the given bone"""
    new_bone: EditBone = bone.id_data.edit_bones.new(bone.name + "_copy")
    new_bone.head = bone.head.copy()
    new_bone.tail = bone.tail.copy()
    new_bone.roll = bone.roll
    new_bone.use_connect = bone.use_connect
    new_bone.use_local_location = bone.use_local_location
    new_bone.use_inherit_rotation = bone.use_inherit_rotation
    new_bone.use_inherit_scale = bone.use_inherit_scale
    new_bone.use_deform = bone.use_deform
    return new_bone

#Binary tools




#encoding FrooxEngine/C# types in binary:






