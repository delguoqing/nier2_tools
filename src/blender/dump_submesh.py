import json
import bpy
D = bpy.data

object = bpy.context.active_object
armt = object.modifiers[0].object
bone_mapping = armt["bone_mapping"] # {bone_id => bone_name}
rev_bone_mapping = dict(zip(bone_mapping.values(), bone_mapping.keys()))

mesh = object.data

vertices_dup = {} #{index => [((u, v), new_index)]}
base_index = len(mesh.vertices)
def resolve_index(index, uv):
    global vertices_dup
    global base_index
    record = vertices_dup.get(index)
    if record is None:
        record = [(uv, index)]
        vertices_dup[index] = record
    for _uv, _index in record:
        if uv == _uv:
            return _index
    new_index = base_index
    base_index += 1
    record.append((uv, new_index))
    return new_index

indices = []
for poly in mesh.polygons:
    assert len(poly.loop_indices) == 3, "ngon not supported, try triangulate before export!"
    for loop_index in poly.loop_indices:
        loop = mesh.loops[loop_index]
        index = loop.vertex_index
        uv = mesh.uv_layers[0].data[loop_index].uv
        resolved_index = resolve_index(index, uv)
        indices.append(resolved_index)

def most_important_bone_weights(v, n):
    result = []
    for group_weight in v.groups:
        group_index = group_weight.group
        weight = group_weight.weight
        result.append((group_index, weight))
    result.sort(key=lambda v: v[1], reverse=True)
    topn = result[:n]
    total_w = 0.0
    for group_index, weight in topn:
        total_w += weight
    if total_w > 0.0:
        topn_norm = []
        for group_index, weight in topn:
            topn_norm.append((group_index, weight / total_w))
        return topn_norm
    else:
        return topn

vertices = [None] * base_index
for i, dup in vertices_dup.items():
    v = mesh.vertices[i]

    vdata = {}
    vdata["position"] = [v.co[0], v.co[2], -v.co[1]]
    vdata["normal"] = [v.normal[0], v.normal[2], -v.normal[1]]
    
    # can't restore index in the bone set, so just we bone id here~
    bone_ids = [0] * 4       # index in bone_set => index in whole file => bone id
    bone_weights = [0] * 4  # should normalize to [0, 255]
    
    top4 = most_important_bone_weights(v, 4)
    for j, (group_index, weight) in enumerate(top4):
        group = object.vertex_groups[group_index]
        bone_id_str = rev_bone_mapping[group.name]
        bone_id = int(bone_id_str)
        bone_ids[j] = bone_id
        bone_weights[j] = int(weight * 255.0)
        
    vdata["bone_ids"] = bone_ids
    vdata["bone_weights"] = bone_weights
    
    for uv, new_i in dup:
        vdata_copy = dict(vdata)    
        vdata_copy["uv"] = [uv[0], uv[1]]
        vertices[new_i] = vdata_copy

fname = object.name + ".json"
fout = open(fname, "w")
json.dump({"vertices": vertices, "indices": indices}, fout)
fout.close()

    
        
    