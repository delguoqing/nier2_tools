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
	