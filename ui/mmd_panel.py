import bpy
from bpy.types import Panel, Context, UILayout
from .main_panel import AvatarToolKit_PT_AvatarToolkitPanel, CATEGORY_NAME
from .panel_layout import get_panel_order, should_open_by_default
from ..core.translations import t
from ..core.common import get_active_armature
from ..functions.tools.mmd import detect_mmd_armature, get_mmd_root


class AvatarToolKit_PT_MMDPanel(Panel):
    """Panel for MMD model fixing and conversion tools"""
    bl_label = t("MMD.panel.label")
    bl_idname = "OBJECT_PT_avatar_toolkit_mmd"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY_NAME
    bl_parent_id = AvatarToolKit_PT_AvatarToolkitPanel.bl_idname
    bl_order = get_panel_order('mmd')
    bl_options = set() if not should_open_by_default('MMD') else {'DEFAULT_CLOSED'}

    def draw(self, context: Context) -> None:
        """Draw the MMD panel interface"""
        layout: UILayout = self.layout
        toolkit = context.scene.avatar_toolkit
        
        main_box: UILayout = layout.box()
        col: UILayout = main_box.column(align=True)
        col.label(text=t("MMD.fixer.title"), icon='ARMATURE_DATA')
        col.separator(factor=0.5)
        
        armature = get_active_armature(context)
        
        if not armature:
            col.label(text=t("MMD.no_armature_selected"), icon='ERROR')
            col.label(text=t("MMD.select_armature_to_fix"))
            return
        
        # Check if the armature appears to be MMD
        is_mmd = detect_mmd_armature(armature)
        mmd_root = get_mmd_root(armature)
        
        if is_mmd:
            col.label(text=t("MMD.armature_name", name=armature.name), icon='CHECKMARK')
            
            if mmd_root:
                col.label(text=t("MMD.model_detected"), icon='INFO')
        
                info_row = col.row()
                info_row.label(text=t("MMD.has_mmd_root"), icon='LINKED')
                
                if hasattr(mmd_root, 'bone_morphs'):
                    morph_count = len(mmd_root.bone_morphs)
                    if morph_count > 0:
                        col.label(text=t("MMD.bone_morphs_count", count=morph_count), icon='SHAPEKEY_DATA')
            else:
                col.label(text=t("MMD.mmd_bones_detected"), icon='INFO')
            
            col.separator(factor=0.5)
            
            options_box = main_box.box()
            options_col = options_box.column(align=True)
            options_col.label(text=t("MMD.fix_options.title"), icon='SETTINGS')
            options_col.separator(factor=0.3)
            options_col.prop(toolkit, 'mmd_make_parent', text=t("MMD.make_armature_parent"))
            options_col.prop(toolkit, 'mmd_rename_armature', text=t("MMD.rename_to_armature"))
            options_col.separator(factor=0.3)
            options_col.label(text=t("MMD.translation_options"), icon='FILE_TEXT')
            options_col.prop(toolkit, 'mmd_translate_names', text=t("MMD.translate_names"))
            
            if toolkit.mmd_translate_names:
                sub_col = options_col.column(align=True)
                sub_col.enabled = toolkit.mmd_translate_names
                row = sub_col.row(align=True)
                row.prop(toolkit, 'mmd_translate_bones', text=t("MMD.translate_bones"), toggle=True)
                row.prop(toolkit, 'mmd_translate_materials', text=t("MMD.translate_materials"), toggle=True)
                row = sub_col.row(align=True)
                row.prop(toolkit, 'mmd_translate_shapekeys', text=t("MMD.translate_shapekeys"), toggle=True)
                row.prop(toolkit, 'mmd_translate_objects', text=t("MMD.translate_objects"), toggle=True)
            
            options_col.separator(factor=0.3)
            options_col.label(text=t("MMD.bone_options"), icon='BONE_DATA')
            options_col.prop(toolkit, 'mmd_remove_twist_bones', text=t("MMD.remove_twist_bones"))
            options_col.prop(toolkit, 'mmd_remove_end_bones', text=t("MMD.remove_end_bones"))
            options_col.prop(toolkit, 'mmd_remove_zero_weight_bones', text=t("MMD.remove_zero_weight_bones"))
            
            options_col.separator(factor=0.3)
            options_col.label(text=t("MMD.scene_options"), icon='SCENE_DATA')
            options_col.prop(toolkit, 'mmd_remove_rigidbodies', text=t("MMD.remove_rigidbodies"))
            options_col.prop(toolkit, 'mmd_join_meshes', text=t("MMD.join_meshes"))
            options_col.prop(toolkit, 'mmd_apply_transforms', text=t("MMD.apply_transforms"))
            
            options_col.separator(factor=0.3)
            options_col.label(text=t("MMD.mesh_options"), icon='MESH_DATA')
            options_col.prop(toolkit, 'mmd_remove_doubles', text=t("MMD.remove_doubles"))
            
            options_col.separator(factor=0.3)
            options_col.label(text=t("MMD.bone_cleanup_options"), icon='BRUSH_DATA')
            options_col.prop(toolkit, 'mmd_delete_bone_constraints', text=t("MMD.delete_bone_constraints"))
            
            options_col.separator(factor=0.3)
            options_col.label(text=t("MMD.advanced_options"), icon='PREFERENCES')
            options_col.prop(toolkit, 'keep_upper_chest', text=t("MMD.keep_upper_chest"))
            options_col.prop(toolkit, 'merge_weights_threshold', text=t("MMD.merge_weights_threshold"))
            
            # Action Button
            main_box.separator(factor=0.5)
            
            # Main fix button
            fix_row = main_box.row()
            fix_row.scale_y = 1.5
            fix_row.operator(
                "avatar_toolkit.fix_mmd_armature",
                text=t("MMD.fix_armature.label"),
                icon='MODIFIER'
            )
            
            # Info Section
            info_box = main_box.box()
            info_col = info_box.column(align=True)
            info_col.label(text=t("MMD.fix_info.title"), icon='INFO')
            info_col.separator(factor=0.2)
            info_col.label(text=t("MMD.fix_info.phase1"))
            info_col.label(text=t("MMD.fix_info.phase2"))
            info_col.label(text=t("MMD.fix_info.translate"))
            info_col.label(text=t("MMD.fix_info.mesh_processing"))
            info_col.label(text=t("MMD.fix_info.bone_visibility"))
            info_col.label(text=t("MMD.fix_info.bone_cleanup"))
            info_col.label(text=t("MMD.fix_info.bone_standardize"))
            info_col.label(text=t("MMD.fix_info.hierarchy_fix"))
            info_col.label(text=t("MMD.fix_info.spine_fix"))
            info_col.label(text=t("MMD.fix_info.eye_processing"))
            
        else:
            col.label(text=t("MMD.armature_name", name=armature.name), icon='ERROR')
            col.label(text=t("MMD.not_mmd_detected"), icon='CANCEL')
            col.separator(factor=0.3)
            
            row = col.row()
            row.enabled = False
            row.operator(
                "avatar_toolkit.fix_mmd_armature",
                text=t("MMD.fix_armature.label"),
                icon='CANCEL'
            )
            
            # Help section for non-MMD models
            help_box = main_box.box()
            help_col = help_box.column(align=True)
            help_col.label(text=t("MMD.detection_failed.title"), icon='QUESTION')
            help_col.label(text=t("MMD.detection_failed.not_mmd_format"))
            help_col.label(text=t("MMD.detection_failed.need_japanese_bones"))
            help_col.label(text=t("MMD.detection_failed.check_bone_names"))
            
            help_col.separator(factor=0.5)
            help_col.label(text=t("MMD.detection_failed.expected_bones"), icon='BONE_DATA')
            help_col.label(text="  • センター, 上半身, 下半身")
            help_col.label(text="  • 首, 頭, 左腕, 右腕")
            help_col.label(text="  • 左足, 右足, etc.")
