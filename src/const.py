# Block Info order:
# Bone, Unk1, Geo, SubMesh, Lod, Unk2, BoneMap, BoneSet, Mat, MeshGroup, MeshGrpMat, Unk3
# Corresponding Block Data order:
# Bone, Unk1, Geo, SubMesh, Lod, MeshGrpMat, Unk2, Boneset, BoneMap, MeshGroup, Mat, Unk3
WMB_BLOCK_ORDER = [
	0,	# Bone		
	1,	# Unk1
	2,	# Geo		
	3,	# SubMesh
	4,	# Lod
	10,	# Unk2
	5,	# BoneMap
	7,	# BoneSet
	6,	# Mat
	9,	# MeshGroup
	8,	# MeshGrpMat
	11,	# Unk3
]

WMB_BLOCK_COUNT = len(WMB_BLOCK_ORDER)