import os
import struct
import collections
import math
import numpy

# BC1
DXT1_HEADER_TEMPLATE = "DDS |\x00\x00\x00\x07\x10\x00\x00\x00\x02\x00\x00\x00\x02\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00 \x00\x00\x00\x04\x00\x00\x00DXT1\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\x10@\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
# BC2
DXT3_HEADER_TEMPLATE = "DDS |\x00\x00\x00\x07\x10\x00\x00\x00\x08\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00 \x00\x00\x00\x04\x00\x00\x00DXT3\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
# BC3
DXT5_HEADER_TEMPLATE = "DDS |\x00\x00\x00\x07\x10\x00\x00\x00\x02\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00 \x00\x00\x00\x04\x00\x00\x00DXT5\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\x10@\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

# lzss decompress
def decompress_lz01(data, init_text_buf=None, debug=False, N=4096, F=17, THRESHOLD=2, decompressed_size=None):
	text_buf = [0] * N
	
	if init_text_buf:
		init_text_buf(text_buf)
		
	dst_buf = []
	src_buf = collections.deque(map(ord, data))
	src_len = len(src_buf)
	group_idx = 0

	r = N - F - 1	# why?
	flags = 0
	bit = 0
		
	while True:
		if decompressed_size is not None:
			if len(dst_buf) == decompressed_size and (flags & 0xFF) == 0:
				break
			elif len(dst_buf) > decompressed_size:
				raise ValueError("Decompressed size do not match!")
		
		try:
			if (flags & 0x100) == 0:
				flags = src_buf.popleft() | 0xFF00
				
				if debug:
					src_offset = src_len - len(src_buf) - 1
					dst_offset = len(dst_buf)
					size = 0
					for i in xrange(8):
						if flags & (1 << i):
							size += 1
						else:
							size += 2
					print "src@offset=%s, dst@offset=%s, flags=%s, %s, size=%s" % \
						(hex(src_offset+12), hex(dst_offset), bin(flags & 0xFF), hex(flags & 0xFF), hex(size))
				bit = 0
				
			if flags & 1:
				c = src_buf.popleft()
				dst_buf.append(c)
				text_buf[r] = c
				r = (r + 1) % N
			else:
				i = src_buf.popleft()
				j = src_buf.popleft()
				offset = i | ((j & 0xF0) << 4)
				length = (j & 0xF) + THRESHOLD + 1
				copy_init = False
				if debug:
					dst_offset = len(dst_buf)
					src_offset = src_len - len(src_buf) - 2
					if dst_offset <= N:
						if (dst_offset < F and (offset >= N - F + dst_offset or offset < N - F)) or \
							(dst_offset >= F and dst_offset <= offset + F < N - F):
							print "refing init window src@offset=%s, dst@offset=%s, window@%s, size=%s" % (hex(src_offset), hex(dst_offset), hex(offset), hex(length))
							print hex(i), hex(j), hex(offset), hex(length)
							copy_init = True
					
				copied = ""
				for k in xrange(length):
					c = text_buf[(offset + k) % N]
					dst_buf.append(c)
					text_buf[r] = c
					r = (r + 1) % N
					if debug:
						copied += chr(c)
				if debug and copy_init:
					print "copied: %s" % repr(copied)
					
			flags >>= 1
			bit += 1
			
		except IndexError, e:
			if decompressed_size is not None and not (len(dst_buf) == decompressed_size and (flags & ((1 << 8 - bit) - 1)) == 0):
				print "Decompress exit with unexpected error:"
				print e
			break
	
	return "".join(map(chr, dst_buf))
	
# makes parsing data a lot easier
def get_getter(data, endian):
	return getter(data, endian)

class getter(object):
	
	def __init__(self, data, endian):
		self.data = data
		self.endian = endian
		self.is_file = isinstance(self.data, file)
		if self.is_file:
			self.offset = self.data.tell()
			self.data.seek(0, 2)
			self.size = self.data.tell()
			self.data.seek(0, self.offset)
		else:
			self.offset = 0
			self.size = len(data)
	
	def seek(self, offset, whence=0):
		assert whence in (0, 1, 2)
		if self.is_file:
			self.data.seek(offset, whence)
			self.offset = self.data.tell()
		else:
			if whence == 0:
				self.offset = offset
			elif whence == 1:
				self.offset += offset
			elif whence == 2:
				self.offset = len(self.data) - offset
	
	def skip(self, size):
		self.seek(size, 1)
	
	def pad(self, size, pad_pattern="\x00"):
		pad_data = self.get_raw(size)
		pattern_size = len(pad_pattern)
		for i in xrange(size / pattern_size):
			assert pad_pattern.startswith(pad_data[i * pattern_size: (i + 1) * pattern_size])
	
	def align(self, size):
		rem = self.offset % size
		if rem:
			self.pad(size - rem)
	
	def get_raw(self, size):
		if self.is_file:
			data_seg = self.data.read(size)
		else:
			data_seg = self.data[self.offset: self.offset + size]
		self.offset += size
		return data_seg
		
	def get(self, fmt, offset=None, force_tuple=False):
		if offset is not None:
			self.seek(offset)
		size = struct.calcsize(fmt)
		data_seg = self.get_raw(size)
		res = struct.unpack(self.endian + fmt, data_seg)
		if not force_tuple and len(res) == 1:
			return res[0]
		return res
	
	def get_cstring(self):
		s = ""
		ch = ""
		while ch != "\x00":
			ch = self.get_raw(1)
			s += ch
		return s.rstrip("\x00")
			
	def block(self, size, endian=None):
		data = self.get_raw(size)
		if endian is None:
			endian = self.endian
		return getter(data, endian)
	
	def assert_end(self):
		assert self.offset == self.size
	
# dump texture atlas layout
def quad_intersect(a, b):
	#print "compare", a, b
	if a[0] >= b[2] or b[0] >= a[2] or a[1] >= b[3] or b[1] >= a[3]:
		return False
	#print "intersect"
	return True

def dump_atlas_layout_brute_force(polys, out_fname):
	if not polys:
		return
	
	# convert raw float values to quads
	quads = []
	for fvals in polys:
		min_x = min(fvals[0: len(fvals): 2])
		max_x = max(fvals[0: len(fvals): 2])
		min_y = min(fvals[1: len(fvals): 2])
		max_y = max(fvals[1: len(fvals): 2])
		quads.append((min_x, min_y, max_x, max_y))
	
	# remove layout image of the same naming convention
	path, ext = os.path.splitext(out_fname)
	os.system("del %s*%s" % (path, ext))
	
	# seperate quads into groups
	quads_groups = [[]]
	polys_groups = [[]]
	for i, quad in enumerate(quads):
		for other_quad in quads_groups[-1]:
			if quad_intersect(quad, other_quad):
				quads_groups.append([])
				polys_groups.append([])
				break
		quads_groups[-1].append(quad)
		polys_groups[-1].append(polys[i])
		
	# dump each quads_group into a seperate atlas layout file
	for grp_idx, polys in enumerate(polys_groups):
		path, ext = os.path.splitext(out_fname)
		_dump_atlas_layout(polys, "%s%d%s" % (path, grp_idx, ext))

def dump_atlas_layout_use_mapping(polys, mapping, out_fname, ref_textures=None):
	if not polys:
		return
	
	tex_count = max(mapping.values()) + 1
	polys_groups = []
	for i in xrange(tex_count):
		polys_groups.append([])
	
	for atlas, tex in sorted(mapping.items()):
		polys_groups[tex].append( polys[atlas] )

	# remove layout image of the same naming convention
	path, ext = os.path.splitext(out_fname)
	os.system("del %s*%s" % (path, ext))
	
	# dump each quads_group into a seperate atlas layout file
	for grp_idx, polys in enumerate(polys_groups):
		path, ext = os.path.splitext(out_fname)
		ref_tex = ref_textures and ref_textures[grp_idx] or None
		_dump_atlas_layout(polys, "%s%d%s" % (path, grp_idx, ext), ref_tex)
		
def point_in_quad(x, y, quad_pos):
	p = numpy.array((x, y, 0))
	a = numpy.array(quad_pos[-1] + (0,))
	sign = None
	for pos in quad_pos:
		b = numpy.array(pos + (0,))
		ab = b - a
		ap = p - a
		ret = numpy.cross(ab, ap)
		_sign = math.copysign(1, ret[2])
		if sign is None:
			sign = _sign
		if sign * _sign < 0:
			return False
		a = b
	return True
	
def gen_dxt1_header(width, height):
	header = DXT1_HEADER_TEMPLATE
	return header[:0xc] + struct.pack("<II", height, width) + header[0x14:]

def gen_dxt3_header(width, height):
	header = DXT3_HEADER_TEMPLATE
	return header[:0xc] + struct.pack("<II", height, width) + header[0x14:]

def gen_dxt5_header(width, height):
	header = DXT5_HEADER_TEMPLATE
	return header[:0xc] + struct.pack("<II", height, width) + header[0x14:]

def decode_dxt1(data, width, height):
	pass

def decode_dxt3(data, width, height):
	pass

def decode_dxt5(data, width, height):
	pass

def hex_to_rgba(col):
	r = ((col >> 24) & 0xFF) / 255.0
	g = ((col >> 16) & 0xFF) / 255.0
	b = ((col >>  8) & 0xFF) / 255.0
	a = ((col >>  0) & 0xFF) / 255.0
	return r, g, b, a

def rgba_to_hex(r, g, b, a):
	return (int(r * 255) << 24) + (int(g * 255) << 16) + (int(b * 255) << 8) + (int(a * 255))

def hex_format(data):
	size = len(data)
	bytes_data = struct.unpack("%dB"%size, data)
	str_list = []
	for i in xrange(size / 4):
		str_list.append("%02x %02x %02x %02x" % tuple(bytes_data[i*4:i*4+4]))
	return " | ".join(str_list)

class CEmpty(object): pass

def load_simple_config(f):
	config = open(f, "r")
	obj = CEmpty()
	for k, v in eval(config.read()).iteritems():
		setattr(obj, k, v)
	return obj

def iter_path(path):
	if isinstance(path, basestring):
		if os.path.isdir(path):
			for top, dirs, files in os.walk(path):
				for fname in files:
					yield os.path.join(top, fname)
		else:
			yield path
	elif callable(path):
		for _path in path():
			yield iter_path(_path)
	else:
		for _path in path:
			yield iter_path(_path)

def beep_error():
	import winsound
	Freq = 750 # Set Frequency To 750 Hertz
	Dur = 300 # Set Duration To 300 ms == 0.3 second
	winsound.Beep(Freq,Dur)

def beep_finish():
	print "\a"
	
def dump_bin(bin_data, file_path, mkdir=False):
	if mkdir:
		d = os.path.split(file_path)[0]
		if d and not os.path.exists(d):
			os.makedirs(d)
	f = open(file_path, "wb")
	f.write(bin_data)
	f.close()
	
# for quick verify
def export_obj(vb, ib, flip_v=False, outpath="test.obj"):
	lines = [
		"s 1",
	]
	if len(vb[0]) >= 3:
		for v in vb:
			lines.append("v %f %f %f" % (v[0], v[1], v[2]))
	if len(vb[0]) >= 5:
		for v in vb:
			u, v = v[3:5]
			if flip_v: v = 1.0 - v
			lines.append("vt %f %f" % (u, v))
	if len(vb[0]) >= 8:
		for v in vb:
			lines.append("vn %f %f %f" % (v[5], v[6], v[7]))
	for i in xrange(len(ib) / 3):
		i1, i2, i3 = ib[i * 3: i * 3 + 3]
		if len(vb[0]) <= 3:	
			lines.append("f %d %d %d" % (i1 + 1, i2 + 1, i3 + 1))
		elif len(vb[0]) <= 5:
			lines.append("f %d/%d %d/%d %d/%d" % (i1 + 1, i1 + 1, i2 + 1, i2 + 1,
												  i3 + 1, i3 + 1))
		elif len(vb[0]) <= 8:
			lines.append("f %d/%d/%d %d/%d/%d %d/%d/%d" % (i1 + 1, i1 + 1, i1 + 1,
														   i2 + 1, i2 + 1, i2 + 1,
														   i3 + 1, i3 + 1, i3 + 1))
	f = open(outpath, "w")
	f.write("\n".join(lines))
	f.close()
	
def export_obj_multi(vb_list, ib_list, flip_v=False, outpath="test.obj"):
	vb = []
	ib = []
	for _vb in vb_list:
		vb.extend(_vb)
	base_i = 0
	for j, _ib in enumerate(ib_list):
		for i in _ib:
			ib.append(i + base_i)
		base_i += len(vb_list[j])
	export_obj(vb, ib, flip_v=flip_v, outpath=outpath)
			
def assert_quat(v, eps=1e-3):
	_eps = math.fabs(v[0]**2 + v[1]**2 + v[2]**2 + v[3]**2 - 1.0)
	assert _eps < eps, ("eps too large: %f vs %f" % (_eps, eps))
	
def print_mat4x4(v):
	mat = ([], [], [], [])
	mat[0][:] = v[:4]
	mat[1][:] = v[4:8]
	mat[2][:] = v[8:12]
	mat[3][:] = v[12:]
	print numpy.matrix(mat)
	
def assert_min_max(_list, _min, _max):
	assert _min == min(_list)
	assert _max == max(_list)
	
def assert_in_bounding_box(point, _min, _max):
	for i in xrange(3):
		assert _min[i] <= point[i] <= _max[i]
		
def euler_to_matrix(rot_x, rot_y, rot_z):
	attitude = rot_z
	bank = rot_y
	heading = rot_y
	sa = math.sin(attitude)
	ca = math.cos(attitude)
	sb = math.sin(bank)
	cb = math.cos(bank)
	sh = math.sin(heading)
	ch = math.cos(heading)
	return numpy.matrix([
		[ch * ca, -ch * sa * cb + sh * sb, ch * sa * sb + sh * cb, 0],
		[sa, ca * cb, -ca * sb, 0],
		[-sh * ca, sh * sa * cb + ch * sb, -sh * sa * sb + ch * cb, 0],
		[0, 0, 0, 1],
	])