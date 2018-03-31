import sys
import os
import numpy
import util
import mot_structs

def parse(mot):
	fourcc = mot.get("4s")
	assert fourcc == "mot\x00"

	version = mot.get("I")
	assert version == 0x20120405

	unk0 = mot.get("I")
	track_offset = mot.get("I")
	track_count = mot.get("I")
	unk1 = mot.get("I")
	name = mot.get("20s").rstrip("\x00")
	print "MOT header: 0x%x, %d, %s" % (unk0, unk1, name)
	tracks = read_track(mot, track_offset, track_count)
	
def read_track(mot, offset, count):
	# read tracks
	tracks = []
	data_offsets = []
	for trk_idx in xrange(count):
		mot.seek(offset + trk_idx * 0xc)
		track = mot_structs.Track()
		track.read(mot)
		track.adjust_offset(offset + trk_idx * 0xc)
		tracks.append(track)
		if track.offset > 0:
			data_offsets.append(track.offset)
	dummy_track = mot_structs.Track()
	dummy_track.read(mot)
	dummy_track.adjust_offset(offset + count * 0xc)
	
	# calculate track chunk data
	data_offsets.append(mot.size)
	data_offsets.sort()
	offset_size = {}
	for i in xrange(len(data_offsets) - 1):
		data_size = data_offsets[i + 1] - data_offsets[i]
		offset_size[data_offsets[i]] = data_size

	# if compress type == 0, then it is a constant value
	for trk_idx in xrange(count):
		track = tracks[trk_idx]
		print "Track %d @ 0x%x" % (trk_idx, offset + trk_idx * 0xc), track,
		if track.offset > 0:
			size = offset_size[track.offset]
			print "0x%x" % size
			if track.comtype in (6, 7):
			 	assert size == 0xc + track.keycount * 0x4
			# elif track.comtype in (3, ):
			# 	pass
			# elif track.comtype in (5, ):
			# 	pass
			# else:
			# 	assert False, "unknown compression type %d" % (track.comtype)
		else:
			print
	print "Dummy Track @ 0x%x" % (mot.offset - 0xc,),  dummy_track

	for trk_idx in xrange(count):
		track = tracks[trk_idx]
		if track.offset:
			print "-----------------Track %d @ 0x%x: compType=%d" % (trk_idx, track.offset, track.comtype)
			track.parse_keyframes(mot)
	return tracks

def parse_file(filepath):
	fp = open(filepath, "rb")
	mot = util.get_getter(fp, "<")
	mot = parse(mot)
	fp.close()
	return mot

if __name__ == "__main__":
	parse_file(sys.argv[1])