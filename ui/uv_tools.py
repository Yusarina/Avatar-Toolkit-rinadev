
import bpy
from ..core.register import register_wrap
from ..functions.translations import t
from ..functions.uv_tools import AvatarToolkit_OT_AlignUVEdgesToTarget
from .panel import draw_title
from .uv_panel import UVTools_PT_MainPanel

@register_wrap
class UVTools_PT_Tools(bpy.types.Panel):
    bl_label = t("Tools.label")
    bl_idname = "OBJECT_PT_avatar_toolkit_uv_tools"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Avatar Toolkit"
    bl_parent_id = UVTools_PT_MainPanel.bl_idname
    bl_order = 3

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        row = layout.row(align=True)
        row.operator(AvatarToolkit_OT_AlignUVEdgesToTarget.bl_idname, text=t("avatar_toolkit.align_uv_edges_to_target.label"), icon='GP_MULTIFRAME_EDITING')