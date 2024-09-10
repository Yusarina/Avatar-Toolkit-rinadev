import bpy
from ..core.register import register_wrap
from .panel import AvatarToolkitPanel
from ..functions.translations import t
from ..functions.remove_doubles_safely import RemoveDoublesSafely, RemoveDoublesSafelyAdvanced
from ..core.common import get_selected_armature

@register_wrap
class AvatarToolkitOptimizationPanel(bpy.types.Panel):
    bl_label = t("Optimization.label")
    bl_idname = "OBJECT_PT_avatar_toolkit_optimization"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Avatar Toolkit"
    bl_parent_id = "OBJECT_PT_avatar_toolkit"
    bl_order = 2

    def draw(self: bpy.types.Panel, context: bpy.types.Context):
        layout = self.layout
        armature = get_selected_armature(context)
        
        if armature:
            layout.label(text=t("Optimization.options.label"), icon='SETTINGS')
            
            row = layout.row()
            row.scale_y = 1.2 
            row.operator("avatar_toolkit.combine_materials", text=t("Optimization.combine_materials.label"), icon='MATERIAL')
            row = layout.row(align=True)
            row.scale_y = 1.2 
            row.operator(RemoveDoublesSafely.bl_idname, text=t("Optimization.remove_doubles_safely.label"), icon='SNAP_VERTEX')
            row.operator(RemoveDoublesSafelyAdvanced.bl_idname, text=t("Optimization.remove_doubles_safely_advanced.label"), icon = "ACTION")
            layout.separator(factor=0.5)
            
            layout.label(text=t("Optimization.joinmeshes.label"), icon='SETTINGS')
            row = layout.row(align=True)
            row.scale_y = 1.2 
            row.operator("avatar_toolkit.join_all_meshes", text=t("Optimization.join_all_meshes.label"), icon='OUTLINER_OB_MESH')
            row.operator("avatar_toolkit.join_selected_meshes", text=t("Optimization.join_selected_meshes.label"), icon='STICKY_UVS_LOC')
            
        else:
            layout.label(text=t("Optimization.select_armature"), icon='ERROR')


