import bpy

# Importers which don't need much code should be added here, however if a importer needs alot of code
# Like the PMX and PMD importers, they should be added to their own files and referenced in the import_types str->lambda dictionary.

#See below comments on how the system works. - @989onan

import importlib.util
import os
import typing
from .import_pmx import import_pmx
from .import_pmd import import_pmd

if importlib.util.find_spec("io_scene_valvesource") is not None:
    #from .....scripts.addons.io_scene_valvesource.import_smd import SmdImporter #<- use this to check if your IDE is working properly. idfk
    from io_scene_valvesource.import_smd import SmdImporter #ignore IDE bitching this is fine, trust me, also above comment should be okay to an IDE usually if set up right. ^_^ - @989onan

def import_multi_files(method = None, directory: typing.Optional[str] = None, files: list[dict[str,str]] = None, filepath: typing.Optional[str] = ""):
    if not files:
        method(directory, filepath)
    else:
        for file in files:
            fullpath = os.path.join(directory,os.path.basename(file["name"]))
            print("run method!")
            method(directory, fullpath)
#each import should map to a type. even in the case that multiple methods should import together, or have the same import method. Make sure the lambdas match so they get grouped together
#In the case of a file importer that takes only one file argument and each one needs individual import, use above method. (example of it in use is ".dae" format)
import_types: dict[str, typing.Callable[[str, list[dict[str,str]], str], None]] = {
    "fbx": (lambda directory, files, filepath : bpy.ops.import_scene.fbx(files=files, directory=directory, filepath=filepath,automatic_bone_orientation=False,use_prepost_rot=False,use_anim=False)),
    "smd": (lambda directory, files, filepath : eval("bpy."+SmdImporter.bl_idname+".(files=files, directory=directory, filepath=filepath)")),
    "dmx": (lambda directory, files, filepath: eval("bpy."+SmdImporter.bl_idname+".(files=files, directory=directory, filepath=filepath)")),
    "gltf": (lambda directory, files, filepath : bpy.ops.import_scene.gltf(files=files, filepath=filepath)),
    "glb": (lambda directory, files, filepath : bpy.ops.import_scene.gltf(files=files, filepath=filepath)),
    "qc": (lambda directory, files, filepath : eval("bpy."+SmdImporter.bl_idname+".(files=files, directory=directory, filepath=filepath)")),
    "obj": (lambda directory, files, filepath : bpy.ops.wm.obj_import(files=files, directory=directory, filepath=filepath)),
    "dae": (lambda directory, files, filepath : import_multi_files(directory=directory, files=files, filepath=filepath, method = (lambda directory, filepath:  bpy.ops.wm.collada_import(filepath=filepath, auto_connect = True, find_chains = True, fix_orientation = True)))),
    "3ds": (lambda directory, files, filepath : bpy.ops.import_scene.max3ds(files=files, directory=directory, filepath=filepath)),
    "stl": (lambda directory, files, filepath : bpy.ops.import_mesh.stl(files=files, directory=directory, filepath=filepath)),
    "mtl": (lambda directory, files, filepath : bpy.ops.wm.obj_import(files=files, directory=directory, filepath=filepath)),
    "x3d": (lambda directory, files, filepath : bpy.ops.import_scene.x3d(files=files, directory=directory, filepath=filepath)),
    "wrl": (lambda directory, files, filepath : bpy.ops.import_scene.x3d(files=files, directory=directory, filepath=filepath)),
    "vmd": (lambda directory, files, filepath : import_multi_files(directory=directory, files=files, filepath=filepath, method = (lambda directory, filepath: bpy.ops.tuxedo.import_mmd_animation(directory=directory, filepath=filepath)))),
    "vrm": (lambda directory, files, filepath: bpy.ops.import_scene.vrm(filepath=filepath)),
    "pmx": (lambda directory, files, filepath : import_pmx(filepath)),
    "pmd": (lambda directory, files, filepath : import_pmd(filepath)),
}

def concat_imports_filter(imports):
    names = ""
    for importer in imports.keys():
        names = names+"*."+importer+";"
    return names

imports = concat_imports_filter(import_types)