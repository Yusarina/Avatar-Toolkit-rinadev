import bpy
from ..core.register import register_wrap
from ..functions.translations import t
from ..core.common import get_armature, get_all_meshes
from ..functions.eyetracking import CreateEyeTrackingSDK2, CreateEyeTrackingSDK3

@register_wrap
class AvatarToolkitEyeTrackingPanel(bpy.types.Panel):
    bl_label = t("EyeTracking.label")
    bl_idname = "OBJECT_PT_avatar_toolkit_eyetracking"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Avatar Toolkit"
    bl_parent_id = "OBJECT_PT_avatar_toolkit"
    bl_order = 6

    def draw(self, context):
        layout = self.layout
        armature = get_armature(context)
        
        if armature:
            layout.label(text=t("EyeTracking.title"), icon='HIDE_OFF')
            layout.separator(factor=0.5)

            row = layout.row(align=True)
            row.scale_y = 1.5
            row.operator(CreateEyeTrackingSDK2.bl_idname, text=t("EyeTracking.create_sdk2"), icon='MESH_CIRCLE')
            
            row = layout.row(align=True)
            row.scale_y = 1.5
            row.operator(CreateEyeTrackingSDK3.bl_idname, text=t("EyeTracking.create_sdk3"), icon='MESH_CIRCLE')
        else:
            layout.label(text=t("EyeTracking.select_armature"), icon='ERROR')
