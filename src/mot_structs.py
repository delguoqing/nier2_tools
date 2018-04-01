import numpy
import struct
import util

class MOT(object):
	pass

class HermitKeyframe(object):
	
	def __init__(self, frameIndex, coeffs):
		self.frameIndex = frameIndex
		self.coeffs = coeffs
		self.p = coeffs[0]
		self.a = coeffs[1]
		self.d = coeffs[2]
		
	def __str__(self):
		return "frame=%d, %g, %g, %g" % (self.frameIndex, self.coeffs[0], self.coeffs[1],
										 self.coeffs[2])
		
class HermitSpline(object):
	
	def __init__(self, keyframes):
		self.keyframes = keyframes
		
	def eval(self, frameIndex):
		if frameIndex <= self.keyframes[0].frameIndex:
			return self.keyframes[0].p
		if frameIndex >= self.keyframes[-1].frameIndex:
			return self.keyframes[-1].p
		i_ = 0
		for i, k in enumerate(self.keyframes):
			if frameIndex < k.frameIndex:
				i_ = i - 1
				break
			if frameIndex == k.frameIndex:
				return k.p
		k1 = self.keyframes[i_]
		k2 = self.keyframes[i_ + 1]
		
		t = 1.0 * (frameIndex - k1.frameIndex) / (k2.frameIndex - k1.frameIndex)
		tt = t * t
		ttt = tt * t
		v = (2 * ttt - 3 * t +1) * k1.p + (ttt - 2 * tt + t) * k1.d + (-2 * ttt + 3 * tt) * k2.p + (ttt - tt) * k2.a;
		return v
	
class PlainKeyframe(object):
	
	def __init__(self, frameIndex, value):
		self.frameIndex = frameIndex
		self.value = value
		
	def __str__(self):
		return "frame=%d, %g" % (self.frameIndex, self.value)
	
class PlainSpline(object):
	
	def __init__(self, keyframes):
		self.keyframes = keyframes
		
	def eval(self, frameIndex):
		if frameIndex <= self.keyframes[0].frameIndex:
			return self.keyframes[0].value
		if frameIndex >= self.keyframes[-1].frameIndex:
			return self.keyframes[-1].value
		return self.keyframes[frameIndex].value
	
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
	
		self.spline = None		

	# just as Bayonetta2, offset is relative
	def adjust_offset(self, offset):
		if self.offset > 0:
			self.offset += offset
			
	def parse_keyframes(self, mot):
		if self.offset <= 0:
			return
		C = util.FloatDecompressor(6, 9, 47)

		mot.seek(self.offset)
		if self.comtype == 1:
			keyframe_data = []
			for i in xrange(self.keycount):
				value = mot.get("f")
				keyframe = PlainKeyframe(i, value)
				keyframe_data.append(keyframe)
				print str(keyframe)
				
			self.spline = PlainSpline(keyframe_data)
			
		elif self.comtype == 2:	# 2 float + 1 unsigned short
			values = mot.get("2f")
			keyframe_data = []
			for i in xrange(self.keycount):
				value = values[0] + values[1] * mot.get("H")
				keyframe = PlainKeyframe(i, value)
				keyframe_data.append(keyframe)
				print str(keyframe)
			self.spline = PlainSpline(keyframe_data)
			
		elif self.comtype == 3:
			values = []
			for v in mot.get("2H"):
				values.append(C.decompress(v))
			keyframe_data = []
			for i in xrange(self.keycount):
				value = values[0] + values[1] * mot.get("B")
				keyframe = PlainKeyframe(i, value)
				keyframe_data.append(keyframe)
				print str(keyframe)
				
			self.spline = PlainSpline(keyframe_data)
			
		elif self.comtype == 4:
			keyframe_data = []
			for i in xrange(self.keycount):
				values = mot.get("HHfff")
				frameIndex = values[0]
				assert values[1] == 0, "this is padding"
				keyframe = HermitKeyframe(frameIndex, values[2:])
				keyframe_data.append(keyframe)
				print str(keyframe)
				
			self.spline = HermitSpline(keyframe_data)
				
		elif self.comtype == 5:
			values = list(mot.get("6f"))
			keyframe_data = []
			
			for i in xrange(self.keycount):
				params = mot.get("4H")
				frameIndex = params[0]
				coeffs = [values[0] + params[1] * values[1],
						  values[2] + params[2] * values[3],
						  values[4] + params[3] * values[5]]
				keyframe = HermitKeyframe(frameIndex, coeffs)
				keyframe_data.append(keyframe)
				print str(keyframe)
			
			self.spline = HermitSpline(keyframe_data)
			
		elif self.comtype == 6:
			# values as [base1, extent1],[base2, extent2],[base3, extent3]
			raw = mot.get_raw(0xc)
			print "raw = ", map(hex, struct.unpack("HHHHHH", raw))

			values = []
			for v in struct.unpack("6H", raw):
				values.append(C.decompress(v))
			print ("values =", values)
			# print ("floatDecompressor", values)
            #
            #
			# values = numpy.frombuffer(raw, dtype=numpy.dtype("<f2"))
			keyframe_data = []
			for i in xrange(self.keycount):
				params = mot.get("4B");

				frameIndex = params[0]
				coeffs = [values[0] + params[1] * values[1],
						  values[2] + params[2] * values[3],
						  values[4] + params[3] * values[5]]
				keyframe = HermitKeyframe(frameIndex, coeffs)
				keyframe_data.append(keyframe)
				print str(keyframe)

			self.spline = HermitSpline(keyframe_data)
		elif self.comtype == 7:
			# values as [base1, extent1],[base2, extent2],[base3, extent3]
			raw = mot.get_raw(0xc)
			print "raw = ", map(hex, struct.unpack("HHHHHH", raw))

			values = []
			for v in struct.unpack("6H", raw):
				values.append(C.decompress(v))
			print ("values =", values)
			# print ("floatDecompressor", values)
            #
            #
			# values = numpy.frombuffer(raw, dtype=numpy.dtype("<f2"))
			keyframe_data = []
			frameIndex = 0
			for i in xrange(self.keycount):
				params = mot.get("4B");

				frameCount = params[0]
				frameIndex += frameCount
				coeffs = [values[0] + params[1] * values[1],
						  values[2] + params[2] * values[3],
						  values[4] + params[3] * values[5]]
				keyframe = HermitKeyframe(frameIndex, coeffs)
				keyframe_data.append(keyframe)
				print str(keyframe)
				
			self.spline = HermitSpline(keyframe_data)
		elif self.comtype == 8:
			# values as [base1, extent1],[base2, extent2],[base3, extent3]
			raw = mot.get_raw(0xc)
			print "raw = ", map(hex, struct.unpack("HHHHHH", raw))

			values = []
			for v in struct.unpack("6H", raw):
				values.append(C.decompress(v))
			print ("values =", values)
			# print ("floatDecompressor", values)
            #
            #
			# values = numpy.frombuffer(raw, dtype=numpy.dtype("<f2"))
			keyframe_data = []
			for i in xrange(self.keycount):
				params = mot.get("H3B");

				frameIndex = params[0]
				coeffs = [values[0] + params[1] * values[1],
						  values[2] + params[2] * values[3],
						  values[4] + params[3] * values[5]]
				keyframe = HermitKeyframe(frameIndex, coeffs)
				keyframe_data.append(keyframe)
				print str(keyframe)

			self.spline = HermitSpline(keyframe_data)			
		else:
			assert False, ("unknown compress type %d" % self.comtype)

	def eval(self, frameIndex):
		if self.is_const:
			return self.const
		return self.spline.eval(frameIndex)
	
	def __str__(self):
		ret = "Bone:%d, type=%d, compress=%d, keynum=%d, " % (
			self.bone_id, self.type, self.comtype, self.keycount)
		if self.is_const:
			ret += "value = %f" % self.const
		else:
			ret += "offset = 0x%x" % self.offset
		return ret
	

