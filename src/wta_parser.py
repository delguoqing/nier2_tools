import os
import sys
import util

class WTA(object):
	
	def __init__(self):
		self.texture_hashes = []
	
def parse(wta):
	ret = WTA()
	
	FOURCC = wta.get("4s")
	assert FOURCC == "WTB\x00"
	wta.skip(4)
	tex_num = wta.get("I")
	offsets = wta.get("5I")
	
	wta.seek(offsets[3])
	tex_hashes = wta.get("%dI" % tex_num, force_tuple=True)
	ret.texture_hashes = tex_hashes
	return ret
