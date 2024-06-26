import bpy
from typing import List, Optional
from bpy.types import Operator, Context, Object
from ..core.register import register_wrap
from ..core.common import fix_uv_coordinates

@register_wrap
class JoinAllMeshes(Operator):
    bl_idname = "avatar_toolkit.join_all_meshes"
    bl_label = "Join All Meshes"
    bl_description = "Join all meshes in the scene"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.mode == 'OBJECT'

    def execute(self, context: Context) -> set:
        self.join_all_meshes(context)
        return {'FINISHED'}

    def join_all_meshes(self, context: Context) -> None:
        if not bpy.data.objects:
            self.report({'INFO'}, "No objects in the scene")
            return

        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')

        meshes: List[Object] = [obj for obj in bpy.data.objects if obj.type == 'MESH']
        for mesh in meshes:
            mesh.select_set(True)

        if bpy.context.selected_objects:
            bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
            bpy.ops.object.join()
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            fix_uv_coordinates(context)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            self.report({'INFO'}, "Meshes joined successfully")
        else:
            self.report({'WARNING'}, "No mesh objects selected")

@register_wrap
class JoinSelectedMeshes(Operator):
    bl_idname = "avatar_toolkit.join_selected_meshes"
    bl_label = "Join Selected Meshes"
    bl_description = "Join selected meshes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.mode == 'OBJECT'

    def execute(self, context: Context) -> set:
        self.join_selected_meshes(context)
        return {'FINISHED'}

    def join_selected_meshes(self, context: Context) -> None:
        selected_objects: List[Object] = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']

        if not selected_objects:
            self.report({'WARNING'}, "No mesh objects selected")
            return

        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')

        for obj in selected_objects:
            obj.select_set(True)

        if bpy.context.selected_objects:
            bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
            bpy.ops.object.join()
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            fix_uv_coordinates(context)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            self.report({'INFO'}, "Selected meshes joined successfully")
        else:
            self.report({'WARNING'}, "No mesh objects selected")

