import sys
import os
import util
from lxml import etree

class NodeInfo(object):
	def read(self, reader):
		self.child_num = reader.get("H")
		self.first_child = reader.get("H")
		self.param_num = reader.get("H")
		self.keyval_idx = reader.get("H")
		
def parse(bxm_reader):
	get = bxm_reader.get
	
	FOURCC = get("4s")	
	reserved = get("I")
	assert FOURCC == "XML\x00" or FOURCC == "BXM\x00"
	assert reserved == 0
	node_num = get("H")
	keyval_num = get("H")
	string_offset_4bytes = get("H")
	string_table_size = get("H")
	string_offset_size = string_offset_4bytes and 4 or 2
	
	# basic node info
	node_infos = []
	for i in xrange(node_num):
		node_info = NodeInfo()
		node_info.read(bxm_reader)
		node_infos.append(node_info)
	
	# raw key/value pairs
	keyvals = []
	for i in xrange(keyval_num):
		if string_offset_4bytes:
			name_offset, value_offset = get("2I")
		else:
			name_offset, value_offset = get("2H")
		keyvals.append((name_offset, value_offset))
	
	# string table
	strings = {}	# rel_offset: string
	#print "string table size = 0x%x" % string_table_size
	string_table_offset = 0x10 + node_num * 0x8 + keyval_num * 2 * string_offset_size
	print "string table offset = 0x%x" % string_table_offset
	while bxm_reader.offset < bxm_reader.size:
		rel_offset = bxm_reader.offset - string_table_offset
		string = bxm_reader.get_cstring()
		#print "offset: 0x%x, %s" % (rel_offset, string)
		strings[rel_offset] = string
		
	# key/value pairs with string offset resolved
	for i in xrange(keyval_num):
		key = strings[keyvals[i][0]]
		if (keyvals[i][1] == 0xFFFF and not string_offset_4bytes) or (keyvals[i][1] == 0xFFFFFFFF and string_offset_4bytes):
			value = ""
		else:
			value = strings[keyvals[i][1]]
		keyvals[i] = (key, value)
	
	for i in xrange(len(node_infos)):
		node_info = node_infos[i]
		keyval_idx = node_info.keyval_idx
		print "Node%d: childN:%d, 1stChild=%d, paramN:%d, keyvalIdx:%d, Data=%s:%s" % (
			i, node_info.child_num, node_info.first_child, node_info.param_num, keyval_idx,
			keyvals[keyval_idx][0], keyvals[keyval_idx][1])
		if node_info.param_num > 0:
			for j in xrange(node_info.param_num):
				keyval_idx += 1
				print "\t", keyvals[keyval_idx][0], ":", keyvals[keyval_idx][1]
		
	return node_infos, keyvals		
			
def gen_xml(i, node_infos, keyvals):
	node_info = node_infos[i]
	key, value = keyvals[node_info.keyval_idx]
	key = key.decode("sjis")
	value = value.decode("sjis")
	node = etree.Element(key)
	if value:
		node.text = value
	for i in xrange(node_info.param_num):
		attrib_key, attrib_val = keyvals[node_info.keyval_idx + i + 1]
		attrib_key = attrib_key.decode("sjis")
		attrib_val = attrib_val.decode("sjis")
		node.attrib[attrib_key] = attrib_val
	for i in xrange(node_info.child_num):
		child_node = gen_xml(node_info.first_child + i, node_infos, keyvals)
		node.append(child_node)
	return node

def convert(fpath):
	fp = open(fpath, "rb")
	bxm_reader = util.get_getter(fp, ">")
	node_infos, keyvals = parse(bxm_reader)
	fp.close()
	
	root = gen_xml(0, node_infos, keyvals)
	xml_str = etree.tostring(root, pretty_print=True, encoding="UTF-8")
	fp = open(fpath.replace(".bxm", ".xml"), "w")
	print fp
	fp.write(xml_str)
	fp.close()
	
def test(path):
	for fpath in util.iter_path(path):
		if fpath.endswith(".bxm"):
			print "processing:", fpath
			convert(fpath)
			
if __name__ == '__main__':
	test(sys.argv[1])