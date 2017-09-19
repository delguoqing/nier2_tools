import sys
import os
import struct

import util

def unpack(data, out_dir=None):
	if not data:
		print "skip empty file!"
		return
	
	dat = util.getter(data, "<")
	
	header = dat.block(0x20)
	fourcc = header.get("4s")
	assert fourcc == "DAT\x00", "incorrect FOURCC, file may be corrupted!"
	file_count = header.get("I")
	file_table_offset = header.get("I")
	ext_table_offset = header.get("I")
	name_table_offset = header.get("I")
	size_table_offset = header.get("I")
	header.skip(8)
	header.assert_end()
	
	print "n=%d, file=0x%x, ext=0x%x, name=0x%x, size=0x%x" % (file_count, file_table_offset, ext_table_offset, name_table_offset, size_table_offset)
	
	dat.seek(file_table_offset)
	offsets = dat.get("%dI" % file_count, force_tuple=True)
	dat.seek(ext_table_offset)
	exts = []
	for i in xrange(file_count):
		exts.append(dat.get("4s").rstrip("\x00"))
	dat.seek(name_table_offset)
	name_buffer_size = dat.get("I")
	names = []
	for i in xrange(file_count):
		names.append(dat.get("%ds" % name_buffer_size).rstrip("\x00"))
	dat.seek(size_table_offset)
	sizes = dat.get("%dI" % file_count, force_tuple=True)
	
	if out_dir and not os.path.isdir(out_dir):
		os.mkdir(out_dir)
		
	for i in xrange(file_count):
		print "file%d,%s,@0x%x,size=0x%x" % (i, names[i], offsets[i], sizes[i])
		assert names[i].endswith(exts[i])
		if out_dir:
			fout = open(os.path.join(out_dir, names[i]), "wb")
			fout.write(data[offsets[i]: offsets[i] + sizes[i]])
			fout.close()
	
def pack(in_dir, out_path):
	size_list = []
	name_list = []
	ext_list = []
	for entry_name in os.listdir(in_dir):
		path = os.path.join(in_dir, entry_name)
		if os.path.isfile(path):
			name_list.append(entry_name)
			ext_list.append(os.path.splitext(entry_name)[1][1:])
			f = open(path, "rb")
			f.seek(0, -1)
			size_list.append(f.tell())
			f.close()
	file_count = len(size_list)
	header_size = 0x20
	ext_table = "\x00".join(ext_list)
	max_name_length = max([len(name) for name in name_list]) + 1
	name_table = "".join([name + "\x00" * (max_name_length - len(name)) for name in name_list])
	name_table = struct.pack("<I", max_name_length) + name_table
	file_table_size = file_count * 0x4
	size_table = struct.pack("<%dI" % file_count, *tuple(size_list))
	# here is an unknown table!
	content_offset = header_size
	content_offset += file_table_size + len(ext_table) + len(name_table) + len(size_table)
	content_offset += 
	
	fout = open(out_path, "wb")
	fout.write("DAT\x00")
	fout.write(struct.pack("<I", file_count))	# file count
	fout.write(struct.pack("<I", header_size))	# file table offset
	
	
	file_table = ""
	for i in xrange(len(files)):
		code
	
	
	
def unpack_all(root):
	for f in util.iter_path(root):
		if not (f.endswith(".dat") or f.endswith(".dtt")):
			continue
		print "handling %s" % f
		fp = open(f, "rb")
		data = fp.read()
		fp.close()
		base, ext = os.path.splitext(f)
		unpack(data, out_dir=base + ext.replace(".", "_") + "_unpacked")

if __name__ == '__main__':
	unpack_all(sys.argv[1])
	