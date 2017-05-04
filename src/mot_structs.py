import numpy

class MOT(object):
	pass

class Track(object):
	def read(self, mot):
		self.bone_id = mot.get("h")
		self.type = mot.get("B") # 0-POSX 1-POSY 2-POSZ 3-ROTX 4-ROTY 5-ROTZ
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
			mot.seek(self.offset + 0xc)
			for i in xrange(self.keycount):
				print "key%d" % i, mot.get("4B")
		elif self.comtype == 6:
			mot.seek(self.offset)
			print mot.get("3f")
			for i in xrange(self.keycount):
				print "key%d" % i, mot.get("4B")
	
	def __str__(self):
		ret = "Bone:%d, type=%d, compress=%d, keynum=%d, " % (
			self.bone_id, self.type, self.comtype, self.keycount)
		if self.is_const:
			ret += "value = %f" % self.const
		else:
			ret += "offset = 0x%x" % self.offset
		return ret
	

