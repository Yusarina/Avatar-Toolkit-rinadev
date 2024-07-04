import bpy
from ..core.register import register_wrap
from .panel import AvatarToolkitPanel
from bpy.types import Context

@register_wrap
class AvatarToolkitToolsPanel(bpy.types.Panel):
    bl_label = "Tools"
    bl_idname = "OBJECT_PT_avatar_toolkit_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Avatar Toolkit"
    bl_parent_id = "OBJECT_PT_avatar_toolkit"

    def draw(self, context: Context):
        layout = self.layout
        layout.label(text="Tools")
        layout.separator(factor=0.5)

        row = layout.row(align=True)
        row.scale_y = 1.5  
        row.operator("avatar_toolkit.convert_to_resonite", text="Translate to Resonite")