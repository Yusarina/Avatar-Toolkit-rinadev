import bpy
from typing import List, Optional
from ...core.common import get_active_armature
from bpy.types import Object, ShapeKey, Mesh, Context, Operator
from functools import lru_cache
from ...core.translations import t

class AvatarToolKit_OT_ExportResonite(Operator):
    bl_idname = 'avatar_toolkit.export_resonite'
    bl_label = t("Importer.export_resonite.label")
    bl_description = t("Importer.export_resonite.desc")
    bl_options = {'REGISTER', 'UNDO'}
    filepath: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context: Context):
        if get_active_armature(context) is None:
            return False
        return True

    def execute(self, context: Context):
        #settings stolen from cats.
        bpy.ops.export_scene.gltf('INVOKE_AREA',
            export_image_format = 'WEBP',
            export_image_quality = 75,
            export_materials = 'EXPORT',
            export_animations = True,
            export_animation_mode = 'ACTIONS',
            export_nla_strips_merged_animation_name = 'Animation',
            export_nla_strips = True)
        return {'FINISHED'}