import numpy

class MOT(object):
	pass

class Track(object):
	def read(self, mot):
		self.bone_id = mot.get("h")
		self.type = mot.get("B") # 0-POSX 1-POSY 2-POSZ 3-ROTX 4-ROTY 5-ROTZ 7-SCALEX 8-SCALEY 9-SCALEZ
		self.comtype = mot.get("B")	# compress type
		self.keycount = mot.get("I")	# keyframe count
		if self.comtype == self.keycount == 0:
			self.const = mot.get("f")
			self.is_const = True
			self.offset = 0x0
		else:
			self.offset = mot.get("I")	# whence=os.SEEK_CUR
			self.const = 0.0
			self.is_const = False
	
	def adjust_offset(self, offset):
		if self.offset > 0:
			self.offset += offset
			
	def parse_keyframes(self, mot):
		if self.offset <= 0:
			return
		mot.seek(self.offset)
		if self.comtype == 7:
			mot.seek(self.offset)
			print mot.get("3f")
			for i in xrange(self.keycount):
				d = mot.get("4B")
				if i == 0:
					assert d[0] == 0, ",".join(map(str, d))
				print "key%d" % i, d
		elif self.comtype == 6:
			mot.seek(self.offset)
			print mot.get("3f")
			for i in xrange(self.keycount):
				d = mot.get("4B")
				if i == 0:
					assert d[0] == 0, ",".join(map(str, d))
				print "key%d" % i, d
	
	def __str__(self):
		ret = "Bone:%d, type=%d, compress=%d, keynum=%d, " % (
			self.bone_id, self.type, self.comtype, self.keycount)
		if self.is_const:
			ret += "value = %f" % self.const
		else:
			ret += "offset = 0x%x" % self.offset
		return ret
	

