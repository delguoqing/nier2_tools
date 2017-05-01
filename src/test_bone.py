def test_bone(bone_infos):
	fp = open("bone_info.py", "w")
	fp.write("DATA = [\n")
	for i, bone_info in enumerate(bone_infos):
		x, y, z = bone_info.world_pos
		x2, y2, z2 = bone_info.world_position_tpose
		l_rx, l_ry, l_rz = bone_info.local_rot
		w_rx, w_ry, w_rz = bone_info.world_rot
		lx, ly, lz = bone_info.local_pos
		fp.write("[%f, %f, %f, %d, %f, %f, %f, %f, %f, %f, %f, %f, %f, %f, %f, %f],\n" % (x, y, z, bone_info.parent_idx, x2, y2, z2, l_rx, l_ry, l_rz, w_rx, w_ry, w_rz, lx, ly, lz))
	fp.write("]\n")
	
	IMPORT_CODE = """import bpy
from mathutils import Euler, Matrix
bpy.ops.object.add(type='ARMATURE', enter_editmode=True)
obj = bpy.context.object
obj.show_x_ray = True
obj.name = "armature"
obj.select = True
bpy.context.scene.objects.active = obj

armt = obj.data

positions_a = []
positions_t = []
parent_indices = []
world_rot = []
local_rot = []
local_pos = []

USE_APOSE = True	# set to False to generate a T-pose armature
for bone_index in range(len(DATA)):
	x, y, z, parent_idx, x2, y2, z2, lrx, lry, lrz, wrx, wry, wrz, lx, ly, lz = DATA[bone_index]
	local_pos.append((lx, ly, lz))
	positions_a.append((x, y, z))
	positions_t.append((x2, y2, z2))
	parent_indices.append(parent_idx)
	local_rot.append(Euler((lrx, lry, lrz)))
	world_rot.append(Euler((wrx, wry, wrz)))
world_pos = positions_a	

if USE_APOSE:
	positions = positions_a
else:
	positions = positions_t

for bone_index in range(len(DATA)):
	x, y, z = positions[bone_index]
	parent_idx = parent_indices[bone_index]
	bone_name = "Bone%d" % bone_index
	bone = armt.edit_bones.new(bone_name)
	bone.head = (x, -z, y)
	bone.tail = (x, -z, y + 0.05)	
		
for bone_index in range(len(DATA)):
	x, y, z = positions[bone_index]
	parent_idx = parent_indices[bone_index]
	bone.use_connect = False
	bone.head = (x, -z, y)
	bone.tail = (x, -z, y + 0.05)
	
	parent = DATA[bone_index][3]
	if parent == -1:
		continue
	bone.parent = armt.edit_bones[parent]
	# verify euler angle parenthesis, and should verify true for pl0000
	#tmp = Euler(local_rot[bone_index])
	#tmp.rotate(world_rot[parent_idx])
	#print("%f %f %f" % (tmp.x - world_rot[bone_index].x, tmp.y - world_rot[bone_index].y, tmp.z - world_rot[bone_index].z))
	
	local_mat = Matrix.Translation(local_pos[bone_index]) * Euler(local_rot[bone_index]).to_matrix().to_4x4()
	world_mat = Matrix.Translation(world_pos[parent_idx]) * Euler(world_rot[parent_idx]).to_matrix().to_4x4() * local_mat
	world_mat2 = Matrix.Translation(world_pos[bone_index]) * Euler(world_rot[bone_index]).to_matrix().to_4x4()
	print(world_mat - world_mat2)
"""
	fp.write(IMPORT_CODE)
	fp.close()