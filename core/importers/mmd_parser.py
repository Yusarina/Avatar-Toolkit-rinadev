import struct
from dataclasses import dataclass
from typing import List, Tuple, Optional
from mathutils import Vector

@dataclass
class PMXVertex:
    position: Vector
    normal: Vector
    uv: Tuple[float, float]
    bone_indices: List[int] 
    bone_weights: List[float]

@dataclass 
class PMXMaterial:
    name: str
    diffuse: Tuple[float, float, float, float]
    specular: Tuple[float, float, float]
    ambient: Tuple[float, float, float]
    texture_index: int
    sphere_texture_index: int
    sphere_mode: int
    toon_texture_index: int
    vertex_count: int

def load_pmx_file(filepath: str):
    """Load and parse PMX file format"""
    with open(filepath, 'rb') as f:
        # Check PMX signature
        if f.read(4) != b'PMX ':
            raise ValueError("Not a valid PMX file")
            
        # Read header
        version = struct.unpack('f', f.read(4))[0]
        header_size = struct.unpack('b', f.read(1))[0]
        
        # Read model info
        encoding = 'utf-16-le' if f.read(1)[0] else 'utf-8'
        additional_vec4s = f.read(1)[0]
        vertex_index_size = f.read(1)[0]
        texture_index_size = f.read(1)[0]
        material_index_size = f.read(1)[0]
        bone_index_size = f.read(1)[0]
        morph_index_size = f.read(1)[0]
        rigid_body_index_size = f.read(1)[0]

        # Read model name
        name_jp = _read_text(f, encoding)
        name_en = _read_text(f, encoding)
        comment_jp = _read_text(f, encoding)
        comment_en = _read_text(f, encoding)

        # Read vertices
        vertex_count = struct.unpack('i', f.read(4))[0]
        vertices = _read_vertices(f, vertex_count)

        # Read faces
        face_count = struct.unpack('i', f.read(4))[0] 
        faces = _read_faces(f, face_count, vertex_index_size)

        # Read textures
        texture_count = struct.unpack('i', f.read(4))[0]
        textures = _read_textures(f, texture_count, encoding)

        # Read materials
        material_count = struct.unpack('i', f.read(4))[0]
        materials = _read_materials(f, material_count, encoding)

        # Read bones
        bone_count = struct.unpack('i', f.read(4))[0]
        bones = _read_bones(f, bone_count, encoding)

        return {
            'name': name_jp,
            'name_en': name_en,
            'vertices': vertices,
            'faces': faces,
            'textures': textures,
            'materials': materials,
            'bones': bones
        }

def _read_text(f, encoding: str) -> str:
    """Read encoded text from file"""
    length = struct.unpack('i', f.read(4))[0]
    if length == 0:
        return ""
    return f.read(length).decode(encoding)

def _read_vertices(f, count: int) -> List[PMXVertex]:
    """Read vertex data"""
    vertices = []
    for _ in range(count):
        pos = struct.unpack('fff', f.read(12))
        normal = struct.unpack('fff', f.read(12))
        uv = struct.unpack('ff', f.read(8))
        
        weight_type = struct.unpack('b', f.read(1))[0]
        
        if weight_type == 0:  # BDEF1
            indices = [struct.unpack('i', f.read(4))[0]]
            weights = [1.0]
        elif weight_type == 1:  # BDEF2
            indices = [struct.unpack('i', f.read(4))[0] for _ in range(2)]
            weights = [struct.unpack('f', f.read(4))[0]]
            weights.append(1.0 - weights[0])
        elif weight_type == 2:  # BDEF4
            indices = [struct.unpack('i', f.read(4))[0] for _ in range(4)]
            weights = [struct.unpack('f', f.read(4))[0] for _ in range(4)]
        elif weight_type == 3:  # SDEF
            indices = [struct.unpack('i', f.read(4))[0] for _ in range(2)]
            weights = [struct.unpack('f', f.read(4))[0]]
            weights.append(1.0 - weights[0])
            # Read SDEF data
            sdef_c = struct.unpack('fff', f.read(12))
            sdef_r0 = struct.unpack('fff', f.read(12))
            sdef_r1 = struct.unpack('fff', f.read(12))
        elif weight_type == 4:  # QDEF
            indices = [struct.unpack('i', f.read(4))[0] for _ in range(4)]
            weights = [struct.unpack('f', f.read(4))[0] for _ in range(4)]
        else:
            raise ValueError(f"Invalid weight type: {weight_type}")
            
        vertices.append(PMXVertex(
            Vector(pos),
            Vector(normal),
            uv,
            indices,
            weights
        ))
    return vertices

def _read_faces(f, count: int, index_size: int) -> List[Tuple[int, int, int]]:
    """Read face indices"""
    faces = []
    for _ in range(count // 3):
        if index_size == 1:
            indices = struct.unpack('BBB', f.read(3))
        elif index_size == 2:
            indices = struct.unpack('HHH', f.read(6))
        elif index_size == 4:
            indices = struct.unpack('III', f.read(12))
        faces.append(indices)
    return faces

def _read_textures(f, count: int, encoding: str) -> List[str]:
    """Read texture paths"""
    return [_read_text(f, encoding) for _ in range(count)]

def _read_materials(f, count: int, encoding: str) -> List[PMXMaterial]:
    """Read material data"""
    materials = []
    for _ in range(count):
        name = _read_text(f, encoding)
        name_en = _read_text(f, encoding)
        
        diffuse = struct.unpack('ffff', f.read(16))
        specular = struct.unpack('fff', f.read(12))
        ambient = struct.unpack('fff', f.read(12))
        
        # Skip flags
        f.read(1)
        
        # Edge color and size
        f.read(16)
        
        # Texture and sphere indices
        texture_index = struct.unpack('i', f.read(4))[0]
        sphere_texture_index = struct.unpack('i', f.read(4))[0]
        sphere_mode = struct.unpack('b', f.read(1))[0]
        
        # Toon texture
        shared_toon_flag = struct.unpack('b', f.read(1))[0]
        if shared_toon_flag:
            toon_texture_index = struct.unpack('b', f.read(1))[0]
        else:
            toon_texture_index = struct.unpack('i', f.read(4))[0]
            
        # Skip comment
        _read_text(f, encoding)
        
        vertex_count = struct.unpack('i', f.read(4))[0]
        
        materials.append(PMXMaterial(
            name=name,
            diffuse=diffuse,
            specular=specular,
            ambient=ambient,
            texture_index=texture_index,
            sphere_texture_index=sphere_texture_index,
            sphere_mode=sphere_mode,
            toon_texture_index=toon_texture_index,
            vertex_count=vertex_count
        ))
    return materials

def _read_bones(f, count: int, encoding: str) -> List[dict]:
    """Read bone data"""
    bones = []
    for _ in range(count):
        bone = {
            'name': _read_text(f, encoding),
            'name_en': _read_text(f, encoding),
            'position': struct.unpack('fff', f.read(12)),
            'parent_index': struct.unpack('i', f.read(4))[0],
            'layer': struct.unpack('i', f.read(4))[0],
            'flags': struct.unpack('H', f.read(2))[0]
        }
        bones.append(bone)
        
        # Skip additional bone data for now
        # TODO: Implement full bone data reading
        
    return bones
