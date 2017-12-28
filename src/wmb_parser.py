import os
import sys
import random
import numpy
import util
import math
import json
import zlib
import test_bone
import struct
import const
import argparse

ENTRY_OFFSET = 0x28	# offset for block (offset, count) pairs
DATA_OFFSET = 0x88	# offset for real block data
MAX_POSSIBLE_BLOCK_NUMBER = (DATA_OFFSET - ENTRY_OFFSET) / 8
		
class WMB(object):
	
	FOURCC = "WMB3"
	
	def is_supported_version(self):
		return self.version == 0x20160116
	
	def valid_versions(self):
		return (0x20160116, 0x20151123, 0x20151001, 0x10000)	# seems like they are using date as version
	
	def read_header(self, wmb):
		FOURCC = wmb.get("4s")
		assert FOURCC == self.FOURCC, "not a WMB3 file!"
		self.version = wmb.get("I")
		assert self.version in self.valid_versions()
		# most wmb has a version of 0x20160116, so I just ignore them a.t.m
		if not self.is_supported_version():
			print "old version is ignored a.t.m"
			return
		dummy = wmb.get("I")
		assert dummy == 0
		
		self.flags = wmb.get("I")
			
		self.bounding_box = wmb.get("6f")	# x,y,z,w,h,d
	
		print FOURCC
		print "version", hex(self.version)
		print "flags", hex(self.flags)
		print "bbox", self.bounding_box
		
		# subblocks
		# dummy.wmb is of size 0x88, which tells us the header size
		subblock_num = MAX_POSSIBLE_BLOCK_NUMBER
		subblocks = []
		subblock_desc = ["Bone", "Unk1", "Geo", "SubMesh", "Lod", "Unk2", "BoneMap", "Boneset", "Mat", "MeshGroup", "MeshGrpMat", "Unk3"]
		for i in xrange(subblock_num):
			subblocks.append(wmb.get("2I"))
			if i < len(subblock_desc):
				desc = subblock_desc[i]
			else:
				desc = ""
			if desc:
				print desc + ":",
			print hex(subblocks[-1][0]), subblocks[-1][1]
		self.subblocks = subblocks
	
	def read_rest(self, wmb):
		subblocks = self.subblocks
		bone_infos = read_bone(wmb, subblocks[0][0], subblocks[0][1])	# hierachy info
		read_rev(wmb, subblocks[1][0], subblocks[1][1])
		#splitter("GeoBuffer")
		geo_buffers = read_geo(wmb, subblocks[2][0], subblocks[2][1], (self.flags & 0x8) and 4 or 2)
	
		# inspect vertex buffer, little experiment
		#for geo_buffer in geo_buffers:
		#	geo_buffer.test()
			
		#splitter("Submesh")
		submesh_infos = read_submesh(wmb, subblocks[3][0], subblocks[3][1])
			
		#splitter("Lod")
		lod_infos = read_lod(wmb, subblocks[4][0], subblocks[4][1])
		
		bonemap = read_bonemap(wmb, subblocks[6][0], subblocks[6][1])	# bonemap {index => bone_id}	all used bone ids
		print_bonemap(bonemap)
		
		bonesets = read_bonesets(wmb, subblocks[7][0], subblocks[7][1])	#
		#splitter("Mat?")
		mats = read_mat(wmb, subblocks[8][0], subblocks[8][1])
		
		#splitter("MeshGroup")
		mesh_group_infos = read_mesh_group(wmb, subblocks[9][0], subblocks[9][1])
		
		# (MeshGroup, MatIndex) pair
		#splitter("MeshGroup/MatIndex Pair")
		read_texid(wmb, subblocks[10][0], subblocks[10][1])

		self.lod_infos = lod_infos
		self.submesh_infos = submesh_infos
		self.geo_buffers = geo_buffers
		self.bone_infos = bone_infos
		self.mesh_group_infos = mesh_group_infos
		self.bonesets = bonesets
		self.bonemap = bonemap	# {index => id}
		self.materials = mats
		self.is_boneset_modified = False
		
		# save raw data for each block, so that we I can focus on modding
		# interesting blocks while leaving other blocks intact without needing
		# to write serialization code for them

		self.raw_data = [""] * const.WMB_BLOCK_COUNT
		block_offset_to_index = {}
		all_offsets = []
		for i, (block_offset, count) in enumerate(subblocks):
			if block_offset == 0:
				continue
			block_offset_to_index[block_offset] = i
			all_offsets.append(block_offset)
		all_offsets.sort()
		for i, block_offset in enumerate(all_offsets):
			j = block_offset_to_index[block_offset]
			if i == len(all_offsets) - 1:
				size = wmb.size - block_offset
			else:
				size = all_offsets[i + 1] - block_offset
			wmb.seek(block_offset)
			self.raw_data[j] = wmb.get_raw(size)

		self.append_data = ""
		self.size = wmb.size

	def get_vertex_index_size(self):
		return (self.flags & 0x8) and 4 or 2
	
	def _get_pack(self, fp):
		def pack(fmt, *args):
			fp.write(struct.pack(fmt, *args))
		return pack
	
	def write_header(self, fp):
		pack = self._get_pack(fp)
		fp.write("WMB3")
		# version, dummy, flags
		pack("<III", self.version, 0, self.flags)
		pack("<6f", *self.bounding_box)
		
	def write(self, fp_out, fp_in):
		"""
		:param fp_out: output file object
		:param fp_in: input file object
		:return:void

		Memory layout:
		|......header.....|
		|..block entries..|		<--- entry start
		|...block data1...|		<--- data_start
		|...block data2...|
		|.................|
		|...block dataN...|

		Modding Note about offset and block size:
		Because this format uses stores global offset directly in files, will any block changes its size,
		any block after that block will have to FIX their offset, which is a pain in ass if we don't know
		the format completely. So, for mesh modding, I'll just decide to keep the block size intact:
		If the new block is smaller than the original one, the file will be padded with zeros.
		If the new block is larger than the original one, I'll just append that data in the end of the file.
		I hope that will work.
		"""
		self.write_header(fp_out)
		
		entry_start = ENTRY_OFFSET
		data_start = DATA_OFFSET

		# pad zeros for offset table
		header_size = fp_out.tell()
		assert header_size == entry_start
		offset_table_size = data_start - entry_start
		fp_out.write("\x00" * offset_table_size)
		
		# -- write blocks --
		write_funcs = []
		for i in xrange(const.WMB_BLOCK_COUNT):
			write_funcs.append(self.get_default_block_data_writer(i))

		# padding to 0x10
		padding = (DATA_OFFSET % 0x10)
		if padding > 0:
			padding = 0x10 - padding
			fp_out.write("\x00" * padding)

		# i -- corresponding entry index
		for i in const.ORDER_D2E:
			entry_writer = self.get_block_entry_writer(i)
			data_writer = write_funcs[i]
			self.append_write_block(fp_out, data_writer, entry_writer)
			
		# append additional data
		fp_out.write(self.append_data)
		
		# write new boneset
		boneset_offset = fp_out.tell()
		boneset_count = len(self.bonesets)
		#	write the data
		boneset_offsettable_size = boneset_count * 8
		curr_boneset_offset = boneset_offset + boneset_offsettable_size
		for i, boneset in enumerate(self.bonesets):
			fp_out.write(struct.pack("<II", curr_boneset_offset, len(boneset)))
			curr_boneset_offset += len(boneset) * 2
		for i, boneset in enumerate(self.bonesets):
			for index_in_boneset in boneset:
				fp_out.write(struct.pack("<H", index_in_boneset))
		#	write the entry
		fp_out.seek(ENTRY_OFFSET + i * 8, os.SEEK_SET)
		fp_out.write(struct.pack("<II", boneset_offset, boneset_count))
		

	def get_default_block_data_writer(self, i):
		def write(fp):
			fp.write(self.raw_data[i])
			n = self.subblocks[i][1]
			return n
		return write
		
	def get_block_entry_writer(self, i):
		def write(fp, offset, count):
			if count > 0:
				fp.seek(ENTRY_OFFSET + i * 8, os.SEEK_SET)
				fp.write(struct.pack("<II", offset, count))
		return write
		
	# helper function: write a block and its header
	def append_write_block(self, fp, data_writer, entry_writer):
		fp.seek(0, os.SEEK_END)
		start_offset = fp.tell()
		count = data_writer(fp)
		entry_writer(fp, start_offset, count)
	
	def get_bone_index_by_bone_id(self, bone_id):
		for _i, _id in enumerate(self.bonemap):
			if bone_id == _id:
				return _i
		return -1
		
	def create_boneset_from_vertices(self, vertices):
		boneset = set()
		for vertex in vertices:
			for i in xrange(4):
				if vertex["bone_weights"][i] == 0:
					continue
				bone_index = self.get_bone_index_by_bone_id(vertex["bone_ids"][i])
				print ("adding", vertex["bone_ids"][i], bone_index)
				boneset.add(bone_index)
		return tuple(boneset)
	
	def add_boneset(self, boneset):
		self.bonesets.append(boneset)
		
	def replace_submesh(self, index, vertices, indices):
		"""
		Each LOD level contains several submesh. This is the smallest piece we can replace.
		In order to do this, we have to do the following:
		1.create new vertex buffer and index buffer. These buffers should include the original
		buffer data, and append new ones. Because one buffer may be referenced by multiple submesh.
		so we have to add buffers to the end of the file.
		2.modify the geometry block to reference the new vertex buffer and index buffer.
		3.modify the submesh info
		"""
		submesh_info = self.submesh_infos[index]
		geo_buffer = self.geo_buffers[submesh_info.geo_idx]
		isize = self.get_vertex_index_size()	# how many bytes to represent a vertex index
		old_vnum = geo_buffer.vnum
		vnum_added = len(vertices)
		new_vnum = old_vnum + vnum_added
		if new_vnum >= (1 << (isize * 8)):
			raise Exception("Too many vertex ..., this is not supported!")
		if geo_buffer.vb_strides[0] != 0x1C:
			raise Exception("vertex buffer format not supported. stride=0x%x" % geo_buffer.vb_strides[0])
		# create new boneset
		boneset = self.create_boneset_from_vertices(vertices)
		print ("boneset", boneset)
		self.add_boneset(boneset)
		new_boneset_idx = len(self.bonesets) - 1
		submesh_info.boneset_idx = new_boneset_idx
		self.is_boneset_modified = True
		# serialize vertex for primary vertex buffer
		def ser_vertex1(v):
			result = []
			result.append(struct.pack("<3f", v["position"][0], v["position"][1], v["position"][2]))
			tangent = [0.2, 0.5, 0.842615]	# we don't have tangent value now, so we just leave it to some random value
			tangent_sign = 1.0
			tangent = map(lambda t: int(255 * (t * tangent_sign * 0.5 + 0.5)), tangent)
			result.append(struct.pack("4B", tangent[0], tangent[1], tangent[2], int((tangent_sign * 0.5 + 0.5) * 255)))
			uv = map(lambda u: numpy.float16(u).view('H'), v["uv"])
			result.append(struct.pack("<2H", uv[0], uv[1]))
			bone_indices = [0] * 4
			for i in xrange(4):
				if v["bone_weights"][i] == 0:
					break
				bone_id = v["bone_ids"][i]				
				bone_index = self.get_bone_index_by_bone_id(bone_id)
				index_in_boneset = -1
				for _i, _bone_index in enumerate(self.bonesets[submesh_info.boneset_idx]):
					if bone_index == _bone_index:
						index_in_boneset = _i
						break
				bone_indices[i] = index_in_boneset
				assert index_in_boneset != -1, "after creating a new boneset, all bones should have an index in that boneset"				
			result.append(struct.pack("4B", bone_indices[0], bone_indices[1], bone_indices[2],
									  bone_indices[3]))
			result.append(struct.pack("4B", v["bone_weights"][0], v["bone_weights"][1], v["bone_weights"][2],
									  v["bone_weights"][3]))
			return "".join(result)
		# serialize vertex buffer for secondary vertex buffer
		def ser_vertex2(v):
			vfmt2 = geo_buffer.vfmt2
			result = []
			if vfmt2 == 10:
				result.append("\x00" * 8)
				normal = map(lambda u: numpy.float16(u).view('H'), v["normal"])
				result.append(struct.pack("<3H", normal[0], normal[1], normal[2]))
				result.append("\x00" * 2)
			elif vfmt2 == 7:
				result.append("\x00" * 4)
				normal = map(lambda u: numpy.float16(u).view('H'), v["normal"])
				result.append(struct.pack("<3H", normal[0], normal[1], normal[2]))
				result.append("\x00" * 2)
			elif vfmt2 == 11:
				result.append("\x00" * 8)
				normal = map(lambda u: numpy.float16(u).view('H'), v["normal"])
				result.append(struct.pack("<3H", normal[0], normal[1], normal[2]))
				result.append("\x00" * 2)
				result.append("\x00" * 4)
			else:
				assert False, "unsupported vertex format for secondary vertex buffer!"
			return "".join(result)

		# create vertex buffer and index buffer
		old_vbufs = geo_buffer.vbufs
		old_indices = geo_buffer.indices
		# fixing vertex buffer
		new_vbufs = [old_vbufs[0] + "".join(map(ser_vertex1, vertices)),	# append 1st vbuf
					 old_vbufs[1] + "".join(map(ser_vertex2, vertices)),]	# append 2nd vbuf
		for i in xrange(2, len(old_vbufs)):				# padding rest vbuf, because we don't know the format yet
			new_vbufs.append(old_vbufs[i] + "\x00" * (vnum_added * geo_buffer.vb_strides[i]))
		# fixing index buffer
		new_indices = old_indices + tuple(map(lambda v: v + old_vnum, indices))
		if isize == 2:
			fmt = "<H"
		else:
			fmt = "<I"
		new_ib = "".join(map(lambda v: struct.pack(fmt, v), new_indices))
		base_offset = self.size + len(self.append_data)	# offset for new buffers
		self.append_data += ("".join(new_vbufs)) + new_ib
		# Modify geometry buffer
		print ("Offset = 0x%x" % base_offset)
		curr_offset = base_offset
		vb_offsets = [0] * 4
		for i in xrange(len(new_vbufs)):
			vb_offsets[i] = curr_offset
			curr_offset += len(new_vbufs[i])
		vb_strides = geo_buffer.vb_strides		# use old stride
		vnum = new_vnum
		vfmt2 = geo_buffer.vfmt2
		ib_offset = curr_offset
		inum = geo_buffer.inum + len(indices)
		dump = create_geo_buffer_dump(vb_offsets, vb_strides, vnum, vfmt2, ib_offset, inum)
		sz = len(dump)
		rdata = self.raw_data[const.WMB_BLK_GEO]
		self.raw_data[const.WMB_BLK_GEO] = rdata[:submesh_info.geo_idx * sz] + dump + rdata[submesh_info.geo_idx * sz + sz:]
		# Modify submesh info
		vmax = new_vnum
		inum = len(indices)
		vstart = 0	# append to the end of the original buffer, because we have shifted indices manually, we don't have to set vstart here
		istart = geo_buffer.inum
		prim_num = inum / 3
		submesh_info_dump = struct.pack("<IiIIIII", submesh_info.geo_idx,
										submesh_info.boneset_idx, vstart, istart, vmax, inum,
										prim_num)
		sz = len(submesh_info_dump)
		rdata = self.raw_data[const.WMB_BLK_SUBMESH]
		self.raw_data[const.WMB_BLK_SUBMESH] = rdata[:index * sz] + submesh_info_dump + rdata[index * sz + sz:]

def create_geo_buffer_dump(vb_offsets, vb_strides, vnum, vfmt2, ib_offset, inum):
	dump = struct.pack("<IIIIIIIIIIII", vb_offsets[0], vb_offsets[1], vb_offsets[2], vb_offsets[3], vb_strides[0],
					   vb_strides[1], vb_strides[2], vb_strides[3], vnum, vfmt2, ib_offset, inum)
	return dump
		
class SubMeshInfo(object):
	
	def read(self, wmb):
		self.geo_idx = wmb.get("I")
		self.boneset_idx = wmb.get("i")
		self.vstart = wmb.get("I")
		self.istart = wmb.get("I")
		self.vnum = wmb.get("I")
		self.inum = wmb.get("I")
		self.prim_num = wmb.get("I")
		
	def __str__(self):
		return "buf:%d,boneset:%d,vstart:%d,istart:%d,vnum:%d,inum:%d,prim_num:%d" % (
			self.geo_idx, self.boneset_idx, self.vstart, self.istart, self.vnum, self.inum,
			self.prim_num)
	
class GeoBuffer(object):
	
	def __init__(self, isize):
		self.isize = isize

	def read(self, wmb):
		"""
		:param wmb:
		:return:

		Memory Layout:
		|vb0_offset,	vb1_offset,	vb2_offset,	vb3_offset|
		|vb0_stride,	vb1_stride,	vb2_stride,	vb3_stride|
		|vnum,			unk,		ib_offset,	inum|
		|...................vb0......................|
		|...................vb1......................|
		|...................vb2......................|
		|...................vb3......................|
		|...................vb4......................|
		|...................ib......................|
		"""
		self._params = wmb.get("12I")
		self.vb_offsets = self._params[:4]
		# a maximum of 4 vertex buffers are allowed, but at most 2 are used in this game
		assert self.vb_offsets[2] == 0 and self.vb_offsets[3] == 0
		self.vb_strides = self._params[4:8]
		assert self.vb_strides[2] == 0 and self.vb_strides[3] == 0
		self.vnum = self._params[8]
		self.vfmt2 = self._params[9]
		self.ib_offset = self._params[10]
		self.inum = self._params[11]
		self.vbufs = []
		for i, vb_off in enumerate(self.vb_offsets):
			if vb_off == 0:
				break
			wmb.seek(vb_off)
			vbuf = wmb.get_raw(self.vb_strides[i] * self.vnum)
			self.vbufs.append(vbuf)
		wmb.seek(self.ib_offset)
		if self.isize == 2:
			self.indices = wmb.get("%dH" % self.inum, force_tuple=True)
		else:
			self.indices = wmb.get("%dI" % self.inum, force_tuple=True)
		#print (self)
		VFMT2STRIDE = {
			10: 0x10,
			11: 0x14,
			7: 0xc,
			5: 0xc,
			4: 0x8,
			14: 0x10,
			12: 0x14,
		}
		assert (self.vb_strides[1] == VFMT2STRIDE[self.vfmt2])		
		self.vertices = self.parse_vb()
		
	def __str__(self):
		return "vb_offs=0x%x/0x%x/%d,%d,vb_strides=0x%x/0x%x/%d/%d,vnum=%d,%d,ib_off=0x%x,inum=%d" % self._params

	def parse_vb(self):
		def conv_tangent(v):
			return v / 255.0 * 2.0 - 1.0
		
		vertices = []
		vb = util.get_getter(self.vbufs[0], "<")
		stride = self.vb_strides[0]
		
		assert stride == 0x1C
		for i in xrange(self.vnum):
			# first vertex buffer
			x, y, z = vb.get("3f")
			tangent = map(conv_tangent, vb.get("4B"))	# The last element being the `sign`
			for j in xrange(3):
				tangent[j] *= tangent[3]
			u, v = numpy.frombuffer(vb.get_raw(4), dtype=numpy.dtype("<f2"))
			bone_indices = vb.get("4B")
			bone_weights = vb.get("4B")
			#assert sum(bone_weights) == 0xFF, "bone_weights sum=0x%x" % sum(bone_weights)
			
			# secondary vertex buffer
			vb2 = util.get_getter(self.vbufs[1], "<")
			if self.vfmt2 == 10:
				# Offset	Sematics	Format
				# 0x0		TEXCOORD1	DXGI_FORMAT_R16G16_FLOAT
				# 0x8		NORMAL		DXGI_FORMAT_R16G16B16A16_FLOAT
				vb2.skip(0x8)
				nx, ny, nz, nw = numpy.frombuffer(vb2.get_raw(8), dtype=numpy.dtype("<f2"))
			elif self.vfmt2 == 7:
				# Offset	Sematics	Format
				# 0x0		TEXCOORD1	DXGI_FORMAT_R16G16_FLOAT
				# 0x4		NORMAL		DXGI_FORMAT_R16G16B16A16_FLOAT
				vb2.skip(0x4)
				nx, ny, nz, nw = numpy.frombuffer(vb2.get_raw(8), dtype=numpy.dtype("<f2"))
			elif self.vfmt2 == 11:
				# Offset	Sematics	Format
				# 0x0		TEXCOORD1	DXGI_FORMAT_R16G16_FLOAT
				# 0x8		NORMAL		DXGI_FORMAT_R16G16B16A16_FLOAT
				# 0x10		TEXCOORD2	DXGI_FORMAT_R16G16_FLOAT
				vb2.skip(0x8)
				nx, ny, nz, nw = numpy.frombuffer(vb2.get_raw(8), dtype=numpy.dtype("<f2"))
				vb2.skip(0x4)
				
			vertices.append({
				"position": (x, y, z),			
				"normal": (nx, ny, nz),			
				"uv": (u, v),					
				"bone_indices": bone_indices,	
				"bone_weights": bone_weights,
			})
			
		return vertices
		
class LodInfo(object):
	
	def read(self, wmb):
		self._params = wmb.get("Ii3I")
		wmb.seek(self._params[0])
		self.name = wmb.get_cstring()
		self.lodlevel = self._params[1]
		self.submesh_start = self._params[2]
		self.submesh_num = self._params[4]
		wmb.seek(self._params[3])
		self.submesh = []
		print str(self)
		for i in xrange(self.submesh_num):
			submesh_info = LodSubmeshInfo()
			print "%d:" % i,
			submesh_info.read(wmb)
			self.submesh.append(submesh_info)
		
	def __str__(self):
		return "%s: level:%d, [%d,%d), 0x%x" % (self.name, self.lodlevel, self.submesh_start, self.submesh_start + self.submesh_num, self._params[3])
		
class LodSubmeshInfo(object):
	
	def read(self, wmb):
		self.geo_index = wmb.get("I")
		self.mesh_group_index = wmb.get("I")
		self.mat_index = wmb.get("I")
		unk0 = wmb.get("i")
		assert unk0 == -1, ("unk0=%d" % unk0)
		# no use, redundant
		self.mesh_group_mat_pair_index = wmb.get("I")
		unk1 = wmb.get("i")	# index into the last block, element size = 0x18
		print "geo:%d, mesh_grp:%d, mat:%d, mesh_grp_mat:%d, unkowns=%d,%d" % (
			self.geo_index, self.mesh_group_index, self.mat_index,
			self.mesh_group_mat_pair_index, unk0, unk1)

class MeshGroupInfo(object):
	
	def read(self, wmb):
		self.params = wmb.get("I6f4I")
		name_offset = self.params[0]
		self.bounding_box = self.params[1:7]
		self.offset2, self.n2, self.offset3, self.n3 = self.params[7:]
		wmb.seek(name_offset)
		self.name = wmb.get_cstring()
		
		# preprocessed data, which is not important for ripping
		
		# related material
		wmb.seek(self.offset2)
		num2 = wmb.get("%dH" % self.n2, force_tuple=True)
		self.bound_materials = num2
		# related bones
		wmb.seek(self.offset3)
		num3 = wmb.get("%dH" % self.n3, force_tuple=True)
		self.bound_bones = num3
		
		print "%s: (%f,%f,%f)-(%f,%f,%f)" % (self.name, self.bounding_box[0], self.bounding_box[1], self.bounding_box[2], self.bounding_box[3], self.bounding_box[4], self.bounding_box[5])
		#print "num2:", len(num2)
		#print num2
		#print "related bones:", len(num3)
		#print num3

class Material(object):
	
	def read(self, wmb):
		params = wmb.get("HHHH10I")
		#assert params[0] == 0x707e0 and params[1] == 0xf0005 # wrong
		# vs/ps stringid?
		strings = [""] * len(params)
		wmb.seek(params[4])
		strings[4] = wmb.get_cstring()	# material name
		wmb.seek(params[5])
		strings[5] = wmb.get_cstring()	# effect name
		wmb.seek(params[6])
		strings[6] = wmb.get_cstring()	# technique
		
		self.name = strings[4]
		self.effect_name = strings[5]
		self.technique_name = strings[6]
		
		# sampler
		sampler_offset = params[8]
		sampler_num = params[9]
		wmb.seek(sampler_offset)
		self.samplers = []	# [(sampler_name, texture_hash)]
		for j in xrange(sampler_num):
			# sampler name, texture hash(which is stored in a wta file or whatever)
			self.samplers.append(list(wmb.get("2I")))
		for j in xrange(sampler_num):
			wmb.seek(self.samplers[j][0])
			self.samplers[j][0] = wmb.get_cstring()
			
		# attributes/uniforms
		var_offset = params[12]
		var_num = params[13]
		wmb.seek(var_offset)
		_vars = []
		for j in xrange(var_num):
			_vars.append(list(wmb.get("If")))
		for j in xrange(var_num):
			wmb.seek(_vars[j][0])
			_vars[j][0] = wmb.get_cstring()
		self.uniforms = _vars
			
		#print ("Mat%d:" % i),
		#print ",".join(map(hex, params))
		#print strings[4:7]
		#print "samplers\n", "\n".join(["%s:0x%x" % tuple(v) for v in self.samplers])
		
	def print_uniforms(self):
		print "vars", ",".join([v[0] + ":%.2f" % v[1] for v in self.uniforms])
	
#DATA_ROOT = r"G:\game\nier_automata\3DMGAME-NieR.Automata.Day.One.Edition-3DM\cpk_unpacked"
DATA_ROOT = r"..\data"
DUMP_MAX_LOD = 0
DUMP_GTB_COMPRESS = True

def parse(wmb):
	wmb_obj = WMB()
	wmb_obj.read_header(wmb)
	
	if not wmb_obj.is_supported_version():
		return wmb_obj

	wmb_obj.read_rest(wmb)
				
	#test_bone.test_bone(bone_infos)

	return wmb_obj
	
def read_submesh(wmb, offset, count):
	if offset == 0:
		return []
	wmb.seek(offset)
	submesh_info_list = []
	for i in xrange(count):
		submesh_info = SubMeshInfo()
		submesh_info.read(wmb)
		submesh_info_list.append(submesh_info)
		print ("%02d:" % i), submesh_info
	return submesh_info_list

def read_geo(wmb, offset, count, isize):
	geo_buffer_list = []
	if offset != 0:
		for i in xrange(count):
			wmb.seek(offset + i * 0x30)
			geo_buf = GeoBuffer(isize)
			geo_buf.read(wmb)
			geo_buffer_list.append(geo_buf)
			print "%d:" % i, geo_buf
		
	return geo_buffer_list

def read_rev(wmb, offset, count):
	rev_offset = offset
	rev_size = count
	# ??	offset, count, size = 0x1, maybe has block padding	
	if rev_offset != 0x0:
		wmb.seek(rev_offset)
		values = wmb.get("%dB" % rev_size)
		
		#print values
		
		values2 = []
		for i in xrange(0, len(values), 2):
			print values[i], values[i + 1]
			values2.append((values[i], values[i + 1]))
		values = values2	
		
		val_map = {}
		for value in values:
			if value not in val_map:
				val_map[value] = 1
			else:
				val_map[value] += 1
		for value in sorted(val_map.keys()):
			print "%r: %d" % (value, val_map[value])

class BoneInfo(object):

	def make_scale_mat(self, sx, sy, sz):
		scale_mat = numpy.matrix([
			[sx, 0, 0, 0],
			[0, sy, 0, 0],
			[0, 0, sz, 0],
			[0, 0, 0, 1]
		])
		return scale_mat
		
	def make_rotate_x(self, rx):
		c = math.cos(rx)
		s = math.sin(rx)
		return numpy.matrix([
			[1, 0, 0, 0],
			[0, c, s, 0],
			[0, -s, c, 0],
			[0, 0, 0, 1]
		])

	def make_rotate_y(self, ry):
		c = math.cos(ry)
		s = math.sin(ry)
		return numpy.matrix([
			[c, 0, -s, 0],
			[0, 1, 0, 0],
			[s, 0, c, 0],
			[0, 0, 0, 1]
		])
	
	def make_rotate_z(self, rz):
		c = math.cos(rz)
		s = math.sin(rz)
		return numpy.matrix([
			[c, s, 0, 0],
			[-s, c, 0, 0],
			[0, 0, 1, 0],
			[0, 0, 0, 1]
		])
	
	def make_rotate_mat(self, rx, ry, rz):
		return self.make_rotate_x(rx) * self.make_rotate_y(ry) * self.make_rotate_z(rz)
	
	def make_trans_mat(self, tx, ty, tz):
		return numpy.matrix([
			[1, 0, 0, 0],
			[0, 1, 0, 0],
			[0, 0, 1, 0],
			[tx, ty, tz, 1]
		])
		
	def read(self, wmb):
		self.bone_id = wmb.get("H")
		self.parent_idx = wmb.get("h")	# index of the parent BoneInfo
		self.local_pos = wmb.get("3f")
		self.local_rot = wmb.get("3f")
		self.local_scale = wmb.get("3f")
		
		# world position for A-pose
		self.world_pos = wmb.get("3f")
		self.world_rot = wmb.get("3f")
		self.world_scale = wmb.get("3f")
		# world position for T-pose
		# bind pose is A-pose, so this position seems useless
		self.world_position_tpose = wmb.get("3f")
	
		s = self.make_scale_mat(self.local_scale[0], self.local_scale[1], self.local_scale[2])
		r = self.make_rotate_mat(self.local_rot[0], self.local_rot[1], self.local_rot[2])
		t = self.make_trans_mat(self.local_pos[0], self.local_pos[1], self.local_pos[2])
		self.local_matrix = s * r * t
		
		s = self.make_scale_mat(self.world_scale[0], self.world_scale[1], self.world_scale[2])
		r = self.make_rotate_mat(self.world_rot[0], self.world_rot[1], self.world_rot[2])
		t = self.make_trans_mat(self.world_pos[0], self.world_pos[1], self.world_pos[2])
		self.world_matrix = s * r * t
		self.offset_matrix = self.world_matrix.getI()
		
	def print_out(self):
		print "Bone id=%d, Low=%d, High=%d, Parent BoneInfo index=%d" % (
			self.bone_id, (self.bone_id & 0xFF), (self.bone_id >> 8), self.parent_idx)
	
	def print_cmp_parent(self, pinfo):
		print "compare ---"
		print "Local Mat"
		print self.local_matrix
		print "World Mat"
		print self.world_matrix
		print "Local Mat * Parent World Mat"
		print self.local_matrix * pinfo.world_matrix
		print "CalcWorld - world"
		diff = self.local_matrix * pinfo.world_matrix - self.world_matrix
		print diff
		assert ((abs(diff) < 1e-3).all())
	
def read_bone(wmb, offset, count):
	bone_offset = offset
	bone_count = count
	if bone_offset == 0:
		return []
	# bone? offset, count, size = 0x58, has block padding to 0x10
	wmb.seek(bone_offset)
	ret = []
	for bone_index in xrange(bone_count):
		bone_info = BoneInfo()
		bone_info.read(wmb)
		ret.append(bone_info)
		
	# print bone info with referrence to its parent
	for i in xrange(bone_count):
		bone_info = ret[i]
		#print "=" * 20
	#	if bone_info.parent_idx != -1:
	#		ret[bone_info.parent_idx].print_out()
		print "-" * 20
		print ("(%d)" % i),
		bone_info.print_out()
	#	if bone_info.parent_idx != -1:
	#		bone_info.print_cmp_parent(ret[bone_info.parent_idx])
		
	# make sure bone id is unique
	bone_ids = set()
	for bone_info in ret:
		bone_ids.add(bone_info.bone_id)
	assert len(bone_ids) == len(ret)
	
	return ret
		
def read_lod(wmb, offset, count):
	lod_list = []
	if offset == 0:
		return lod_list
	
	for i in xrange(count):
		wmb.seek(offset + i * 0x14)
		lod = LodInfo()
		lod.read(wmb)
		lod_list.append(lod)
	return lod_list
	
def read_mesh_group(wmb, offset, num):
	if offset == 0:
		return []
	mesh_group_infos = []
	for i in xrange(num):
		wmb.seek(offset + i * 0x2c)
		mesh_group_info = MeshGroupInfo()
		mesh_group_info.read(wmb)
		mesh_group_infos.append(mesh_group_info)
	return mesh_group_infos

def read_mat(wmb, offset, num):
	mat_list = []
	if offset == 0:
		return mat_list
	for i in xrange(num):
		wmb.seek(offset + i * 0x30)
		mat = Material()
		mat.read(wmb)
		mat_list.append(mat)
		
		#print "Mat %d" % i,
		#mat.print_uniforms()
	return mat_list

def dump_submesh(submesh_info, geo_buffers, outpath):
	geo_buffer = geo_buffers[submesh_info.geo_idx]
	
	vertices = []
	for i in xrange(geo_buffer.vnum):
		x, y, z = geo_buffer.vertices[i]["position"]
		u, v = geo_buffer.vertices[i]["uv"]
		#vertices.append((x, y, z, u, v))
		nx, ny, nz = geo_buffer.vertices[i]["normal"]
		vertices.append((x, y, z, u, v, nx, ny, nz))
	indices = geo_buffer.indices[submesh_info.istart: submesh_info.istart + submesh_info.inum]
	
	util.export_obj(vertices, indices, flip_v=True, outpath=outpath)

def read_texid(wmb, offset, num):
	if offset == 0:
		return []
	texid_list = []
	wmb.seek(offset)
	for i in xrange(num):
		texid_list.append(wmb.get("2I"))
		#print i, texid_list[-1]
	return texid_list
	
def read_bonesets(wmb, offset, num):
	if offset == 0:
		return []
	bonesets = []
	wmb.seek(offset)
	data = wmb.get("%dI" % (2 * num))
	for i in xrange(num):
		wmb.seek(data[i * 2])
		bonesets.append(wmb.get("%dH" % data[i * 2 + 1], force_tuple=True))
	return bonesets
		
def read_bonemap(wmb, offset, num):
	if offset == 0:
		return []
	wmb.seek(offset)
	return wmb.get("%dI" % num, force_tuple=True)

def print_bonemap(bonemap):
	print ("bonemap:")
	for i, bone_id in enumerate(bonemap):
		print ("%d: %d" % (i, bone_id))

def test(path):
	for fpath in util.iter_path(path):
		if fpath.endswith(".wmb"):
			do_test(fpath)

def test_rand(root):
	fpath = random.choice(list(util.iter_path(root)))
	do_test(fpath)

def do_test(fpath):
	print "processing:", fpath
	fp = open(fpath, "rb")
	wmb = util.get_getter(fp, "<")
	wmb = parse(wmb)
	fp.close()
	
	if args.dry_run:
		return
	if args.format == "gtb":
		dump_wmb(wmb, outpath=fpath.replace(".wmb", ".gtb"))
	else:
		for lodlv in xrange(DUMP_MAX_LOD + 1):
			lod_info = wmb.lod_infos[lodlv]
			for submesh_idx in xrange(lod_info.submesh_start, lod_info.submesh_start + lod_info.submesh_num):
				outpath = lod_info.name + "_" + str(submesh_idx) + ".obj"
				dump_submesh(wmb.submesh_infos[submesh_idx], wmb.geo_buffers, outpath)
				
def parse_isize(wmb):
	FOURCC = wmb.get("4s")
	assert FOURCC == "WMB3", "not a WMB3 file!"
	version = wmb.get("I")
	# most wmb has a version of 0x20160116, so I just ignore them a.t.m
	assert version in (0x20160116, 0x20151123, 0x20151001, 0x10000)	# seems like they are using date as version
	if version != 0x20160116:
		print "old version is ignored a.t.m"
		return 0
	
	assert wmb.get("I") == 0
	
	flags = wmb.get("I")
	if (flags & 0x8) == 0:
		return 1
	else:
		return 0
	
def do_test_isize(fpath):
	fp = open(fpath, "rb")
	wmb = util.get_getter(fp, "<")
	res = parse_isize(wmb)
	fp.close()
	
	if res:
		print fpath
		
#do_test = do_test_isize

def splitter(name="", dash_count=20):
	print "-" * dash_count,
	if name:
		print name,
	print "-" * dash_count
	
# only 19 files has different version than 0x20160116
def collect_version(path):
	version_dict = {}
	for version in (0x20160116, 0x20151123, 0x20151001, 0x10000):
		version_dict[version] = []
	for fpath in util.iter_path(path):
		if fpath.endswith(".wmb"):
			print "processing:", fpath
			fp = open(fpath, "rb")
			wmb = util.get_getter(fp, "<")
			version_dict[wmb.get("I", offset=0x4)].append(os.path.split(fpath)[1])
			fp.close()
	return version_dict

def export_gtb(wmb, lod=0):
	gtb = {"objects": {}}
	# mesh
	lod_info = wmb.lod_infos[lod]
	for i, lod_submesh_info in enumerate(lod_info.submesh):
		submesh_index = i + lod_info.submesh_start
		submesh_info = wmb.submesh_infos[submesh_index]
		# There're two geometry block indices, one is not neccessary
		assert submesh_info.geo_idx == lod_submesh_info.geo_index, "This should equal!"
		geo_buffer = wmb.geo_buffers[lod_submesh_info.geo_index]
		mesh_group_info = wmb.mesh_group_infos[lod_submesh_info.mesh_group_index]
		
		mesh_name = mesh_group_info.name + str(submesh_index)
		print "dumping %s" % mesh_name

		msh = {
			"flip_v": 1,
			"double sided": 0,
			"shade_smooth": True,
		}
		
		has_bone = (wmb.bonesets and submesh_info.boneset_idx != -1)
		
		index_num = submesh_info.inum
		msh["indices"] = geo_buffer.indices[submesh_info.istart: submesh_info.istart + submesh_info.inum]
		min_index = min(msh["indices"])
		max_index = max(msh["indices"])
		msh["indices"] = map(lambda v: v - min_index, msh["indices"])
		
		vertex_num = max_index + 1 - min_index
		print "inum, vnum", index_num, vertex_num, min_index, max_index, len(msh["indices"]), submesh_info.vnum
		msh["vertex_num"] = vertex_num
		msh["index_num"] = index_num
		msh["position"] = []
		msh["uv_count"] = 1
		msh["normal"] = []
		msh["uv0"] = []
		msh["max_involved_joint"] = has_bone and 4 or 0
		if has_bone:
			msh["joints"] = []
			msh["weights"] = []
		for v in geo_buffer.vertices[min_index: max_index + 1]:
			msh["position"].extend(v["position"])
			msh["normal"].extend(map(float, v["normal"]))
			msh["uv0"].extend(map(float, v["uv"]))	# float16 is not JSON serializable
			if has_bone:
				msh["joints"].extend(v["bone_indices"])
				msh["weights"].extend(v["bone_weights"])
		
		mat = wmb.materials[lod_submesh_info.mat_index]
		msh["textures"] = []
		for sampler_name, texture_hash in mat.samplers:
			# texture_path, uv_layer, hint01, hint02, ...
			msh["textures"].append(("%08X.dds" % texture_hash, 0, sampler_name))

		if has_bone:
			boneset = wmb.bonesets[submesh_info.boneset_idx]
			joint_min = min(msh["joints"])
			joint_max = max(msh["joints"])
			#print "joint min = %d, max = %d, bound_bones = %d" % (joint_min, joint_max, len(boneset))
			#print "bound bones:", ",".join(map(str, boneset))
			# map joint
			for vi in xrange(len(msh["joints"])):
				j, w = msh["joints"][vi], msh["weights"][vi]
				if not w:
					continue
				msh["joints"][vi] = wmb.bonemap[boneset[j]]
			msh["weights"] = map(lambda wint: wint / 255.0, msh["weights"])
		
		gtb["objects"][mesh_name] = msh
	# skeleton
	bone_num = len(wmb.bone_infos)
	if bone_num > 0:
		skel = gtb["skeleton"] = {}
		skel["name"] = []
		skel["parent"] = [-1] * bone_num
		skel["matrix"] = []
		skel["bone_id"] = []
		for i, bone_info in enumerate(wmb.bone_infos):
			bone_id = bone_info.bone_id
			skel["parent"][i] = bone_info.parent_idx
			skel["matrix"].extend(bone_info.local_matrix.getA1())
			skel["bone_id"].append(bone_id)
			skel["name"].append("Bone%d" % bone_id)

	return gtb
	
def dump_wmb(wmb, outpath="a.gtb"):
	gtb = export_gtb(wmb, lod=0)
	if DUMP_GTB_COMPRESS:
		fp = open(outpath, "wb")
		fp.write("GTB\x00")
		compressor = zlib.compressobj()
		for chunk in json.JSONEncoder().iterencode(gtb):
			fp.write(compressor.compress(chunk))
		fp.write(compressor.flush())
	else:
		fp = open(outpath, "w")
		json.dump(gtb, fp, indent=2, sort_keys=True, ensure_ascii=True)
	fp.close()

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description="Nier2: Automata model tool.")
	parser.add_argument("cmd", help="command you want to perform", choices=["parse", "mod"])
	parser.add_argument("--wmb", action="store", dest="in_path", type=str, help="Input file(s). A file or a directory.")
	parser.add_argument("--random", action="store_true", default=False)
	parser.add_argument("--dry_run", action="store_true", default=False)
	parser.add_argument("--format", action="store", type=str, choices=["gtb", "obj"], default="gtb")
	parser.add_argument("--meshes", action="store", type=int, nargs="*", help="Indices of meshes that will be replaced")
	parser.add_argument("--mesh_reps", action="store", type=str, nargs="*", help="json files which is the replacement of meshes.")
	
	args = parser.parse_args()
		
	if args.cmd == "mod":
		in_path = args.in_path
		out_path = os.path.split(in_path)[1]
		
		fp_in = open(in_path, "rb")
		wmb = util.get_getter(fp_in, "<")
		wmb = parse(wmb)
		
		for i in xrange(len(args.meshes)):
			index = args.meshes[i]
			json_file = args.mesh_reps[i]
			fjson = open(json_file, "r")
			rep = json.load(fjson)
			fjson.close()
			wmb.replace_submesh(index, rep["vertices"], rep["indices"])
		
		fp_out = open(out_path, "wb")
		wmb.write(fp_out, fp_in);
		
		fp_in.close()
		fp_out.close()
	elif args.random:
		test_rand(DATA_ROOT)
	elif args.in_path is None:
		test(DATA_ROOT)
	else:
		test(args.in_path)