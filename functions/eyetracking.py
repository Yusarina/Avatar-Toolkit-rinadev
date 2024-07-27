import bpy
import math
from ..core.register import register_wrap
from ..functions.translations import t
from ..core.common import get_selected_armature, select_current_armature, get_all_meshes, has_shapekeys, sort_shape_keys

@register_wrap
class CreateEyeTrackingSDK2(bpy.types.Operator):
    bl_idname = 'avatar_toolkit.create_eye_tracking_sdk2'
    bl_label = t('EyeTracking.create_sdk2')
    bl_description = t('EyeTracking.create_sdk2_desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return get_selected_armature(context) is not None and get_all_meshes(context)

    def execute(self, context):
        armature = get_selected_armature(context)
        select_current_armature(context)
        bpy.ops.object.mode_set(mode='EDIT')

        # Create eye bones
        left_eye = armature.data.edit_bones.new('LeftEye')
        right_eye = armature.data.edit_bones.new('RightEye')

        # Set eye bone positions (you may need to adjust these values)
        left_eye.head = (0.03, 0, 1.7)
        left_eye.tail = (0.03, 0.1, 1.7)
        right_eye.head = (-0.03, 0, 1.7)
        right_eye.tail = (-0.03, 0.1, 1.7)

        # Parent eye bones to head (assuming 'Head' bone exists)
        head_bone = armature.data.edit_bones.get('Head')
        if head_bone:
            left_eye.parent = head_bone
            right_eye.parent = head_bone

        bpy.ops.object.mode_set(mode='OBJECT')

        # Create shape keys for blinking
        mesh = get_all_meshes(context)[0]  # Assuming the first mesh is the one we want
        if not has_shapekeys(mesh):
            mesh.shape_key_add(name='Basis')

        blink_left = mesh.shape_key_add(name='vrc.blink_left')
        blink_right = mesh.shape_key_add(name='vrc.blink_right')

        # Set up vertex groups for eyes
        left_eye_group = mesh.vertex_groups.new(name='LeftEye')
        right_eye_group = mesh.vertex_groups.new(name='RightEye')

        sort_shape_keys(mesh)

        self.report({'INFO'}, t('EyeTracking.sdk2_success'))
        return {'FINISHED'}

@register_wrap
class CreateEyeTrackingSDK3(bpy.types.Operator):
    bl_idname = 'avatar_toolkit.create_eye_tracking_sdk3'
    bl_label = t('EyeTracking.create_sdk3')
    bl_description = t('EyeTracking.create_sdk3_desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return get_selected_armature(context) is not None and get_all_meshes(context)

    def execute(self, context):
        armature = get_selected_armature(context)
        select_current_armature(context)
        bpy.ops.object.mode_set(mode='EDIT')

        # Create eye bones
        left_eye = armature.data.edit_bones.new('LeftEye')
        right_eye = armature.data.edit_bones.new('RightEye')

        # Set eye bone positions (you may need to adjust these values)
        left_eye.head = (0.03, 0, 1.7)
        left_eye.tail = (0.03, 0.1, 1.7)
        right_eye.head = (-0.03, 0, 1.7)
        right_eye.tail = (-0.03, 0.1, 1.7)

        # Parent eye bones to head (assuming 'Head' bone exists)
        head_bone = armature.data.edit_bones.get('Head')
        if head_bone:
            left_eye.parent = head_bone
            right_eye.parent = head_bone

        # Set bone roll to 0 for proper orientation
        left_eye.roll = 0
        right_eye.roll = 0

        bpy.ops.object.mode_set(mode='OBJECT')

        # Create shape keys for blinking and eye movement
        mesh = get_all_meshes(context)[0]  # Assuming the first mesh is the one we want
        if not has_shapekeys(mesh):
            mesh.shape_key_add(name='Basis')

        blink_left = mesh.shape_key_add(name='vrc.blink_left')
        blink_right = mesh.shape_key_add(name='vrc.blink_right')
        look_up = mesh.shape_key_add(name='vrc.v_lookUp')
        look_down = mesh.shape_key_add(name='vrc.v_lookDown')
        look_left = mesh.shape_key_add(name='vrc.v_lookLeft')
        look_right = mesh.shape_key_add(name='vrc.v_lookRight')

        # Set up vertex groups for eyes
        left_eye_group = mesh.vertex_groups.new(name='LeftEye')
        right_eye_group = mesh.vertex_groups.new(name='RightEye')

        sort_shape_keys(mesh)

        self.report({'INFO'}, t('EyeTracking.sdk3_success'))
        return {'FINISHED'}
