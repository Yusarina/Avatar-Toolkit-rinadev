# GPL License
# Avatar Toolkit MMD Converter - Completion (Phase 13)

import bpy
from typing import Optional
from bpy.types import Context, Object

from ....core.logging_setup import logger
from ....core.common import (
    set_active,
    unselect_all,
    SavedData,
)


def restore_state(context: Context, saved_data: Optional[SavedData],
                  armature: Object) -> None:
    """
    Restore saved state after MMD conversion.
    
    Args:
        context: Blender context
        saved_data: SavedData object with saved state
        armature: The armature object to set as active
    """
    try:
        # Ensure we're in object mode
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # Restore saved data if available
        if saved_data:
            try:
                saved_data.load(
                    load_mode=True,
                    load_select=False,  # Don't restore selection, keep armature selected
                    load_hide=True,
                    load_active=False   # We'll set armature as active
                )
            except Exception as e:
                logger.debug(f"Could not fully restore saved data: {e}")
        
        # Ensure armature is active and selected
        unselect_all()
        set_active(armature)
        
        logger.debug("Restored state after MMD conversion")
        
    except Exception as e:
        logger.warning(f"Error restoring state: {e}")


def switch_to_object_mode(context: Context) -> bool:
    """
    Ensure we're in object mode.
    
    Returns:
        True if successfully in object mode
    """
    try:
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        return True
    except Exception as e:
        logger.warning(f"Could not switch to object mode: {e}")
        return False


def display_completion_message(operator, success: bool, 
                                stats: Optional[dict] = None) -> None:
    """
    Display completion message to user.
    
    Args:
        operator: The Blender operator (for self.report)
        success: Whether the operation was successful
        stats: Optional dictionary of statistics to display
    """
    if success:
        if stats:
            msg_parts = ["MMD armature fix completed:"]
            
            if stats.get('bones_renamed', 0) > 0:
                msg_parts.append(f"{stats['bones_renamed']} bones renamed")
            if stats.get('weights_transferred', 0) > 0:
                msg_parts.append(f"{stats['weights_transferred']} weights transferred")
            if stats.get('bones_removed', 0) > 0:
                msg_parts.append(f"{stats['bones_removed']} bones removed")
            
            message = ", ".join(msg_parts) if len(msg_parts) > 1 else "MMD armature fix completed successfully"
        else:
            message = "MMD armature fix completed successfully"
        
        operator.report({'INFO'}, message)
        logger.info(message)
    else:
        message = "MMD armature fix failed - check console for details"
        operator.report({'ERROR'}, message)
        logger.error(message)


def finalize_armature(context: Context, armature: Object) -> None:
    """
    Final armature setup after all processing.
    
    Args:
        context: Blender context
        armature: The armature object
    """
    try:
        # Ensure armature is visible
        armature.hide_viewport = False
        armature.hide_set(False)
        
        # Set display mode to something reasonable
        armature.data.display_type = 'OCTAHEDRAL'
        
        # Ensure pose position is REST
        armature.data.pose_position = 'REST'
        
        # Update view layer
        context.view_layer.update()
        
        logger.debug("Finalized armature settings")
        
    except Exception as e:
        logger.warning(f"Error finalizing armature: {e}")


def cleanup_scene(context: Context) -> int:
    """
    Clean up scene after MMD conversion.
    Removes orphan data blocks and unused objects.
    
    Returns:
        Number of items cleaned up
    """
    cleaned = 0
    
    try:
        # Purge orphan data
        result = bpy.ops.outliner.orphans_purge(
            do_local_ids=True, 
            do_linked_ids=True, 
            do_recursive=True
        )
        
        if result == {'FINISHED'}:
            logger.debug("Purged orphan data blocks")
            cleaned += 1
            
    except Exception as e:
        logger.debug(f"Could not purge orphans: {e}")
    
    return cleaned
