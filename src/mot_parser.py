import sys
import os
import numpy
import zlib
import json
import util
import mot_structs

COMPRESS = True

def parse(mot, dump=True):
	fourcc = mot.get("4s")
	assert fourcc == "mot\x00"

	version = mot.get("I")
	assert version == 0x20120405

	unk0 = mot.get("H")
	frame_count = mot.get("H")
	track_offset = mot.get("I")
	track_count = mot.get("I")
	unk1 = mot.get("I")
	name = mot.get("20s").rstrip("\x00")
	print "MOT header: 0x%x, %d, name=%s, frame=%d" % (unk0, unk1, name, frame_count)
	tracks = read_track(mot, track_offset, track_count)

	if dump:
		gtba = {
			"pose": {},
			"animations": {},
		}
		gtba["animations"][name] = dump_motion(frame_count, tracks);
		filename = name + ".gtba"
		write_file(gtba, filename);

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
		if track.offset > 0:
			size = offset_size[track.offset]
			if track.comtype in (6, 7):
			 	assert size == align4(0xc + track.keycount * 0x4)
			elif track.comtype == 5:
				assert size == align4(0x18 + track.keycount * 0x8)
			elif track.comtype == 3:
				assert size == align4(0x4 + track.keycount * 0x1)
			elif track.comtype == 2:
				assert size == align4(0x8 + track.keycount * 0x2)
			elif track.comtype == 8:
				# 6 unsigned short + (unsigned short frameIndex + 3 byte coeffs)
				assert size == align4(0xc + track.keycount * 0x5)
			elif track.comtype == 4:
				# no header + 0x10
				assert size == align4(0x0 + track.keycount * 0x10)
			elif track.comtype == 1:
				# floats
				assert size == align4(0x0 + track.keycount * 0x4)
			else:
			 	assert False, "unknown compression type %d" % (track.comtype)

	hdr_offset = offset
	for trk_idx in xrange(count):
		track = tracks[trk_idx]
		if track.comtype != 0:
			size = offset_size[track.offset]
		else:
			size = 0
			
		print "Track %d hdr@0x%x, size=0x%x" % (trk_idx, hdr_offset, size),
		print track
		
		if track.offset:
			track.parse_keyframes(mot)
		hdr_offset += 0xc
		
	print "Dummy Track @ 0x%x" % hdr_offset,
	print dummy_track
	
	return tracks

# align to 4 bytes
def align4(size):
	rem = size % 4
	if rem:
		size += 4 - rem
	return size

def parse_file(filepath):
	fp = open(filepath, "rb")
	mot = util.get_getter(fp, "<")
	mot = parse(mot)
	fp.close()
	return mot

def write_file(gtba, out_path):
	data = json.dumps(gtba, indent=2, sort_keys=True, ensure_ascii=True)
	if COMPRESS:
		f = open(out_path, "wb")
		f.write("GTBA" + zlib.compress(data))
	else:
		f = open(out_path, "w")
		f.write(data)
	f.close()

def dump_motion(frame_count, tracks):
	evaluated_tracks = {}	# {bone_id: [POSX, POSY, POSZ, ROTX, ROTY, ROTZ, SCALEX, SCALEY, SCALEZ]}

	# evaluate all tracks for all bones
	for track in tracks:
		bone_tracks = evaluated_tracks.setdefault(track.bone_id, [None] * 9)
		frames = []
		for i in xrange(frame_count):
			frames.append(track.eval(i))
		bone_tracks[track.type] = frames

	# fill in missing tracks
	default_value = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
	for bone_id, bone_tracks in evaluated_tracks.iteritems():
		for i in xrange(len(bone_tracks)):
			if bone_tracks[i] is None:
				bone_tracks[i] = [default_value[i]] * frame_count

	# combine separated tracks
	motion_data = {}
	for bone_id, bone_tracks in evaluated_tracks.iteritems():
		pos_frames = []
		rot_frames = []
		scale_frames = []
		for i in xrange(frame_count):
			pos_frames.append((i, bone_tracks[0][i], bone_tracks[1][i], bone_tracks[2][i]))
			rotx = bone_tracks[3][i]
			roty = bone_tracks[4][i]
			rotz = bone_tracks[5][i]
			# TODO: need to convert euler angles to quaternion
			scale_frames.append((i, bone_tracks[6][i], bone_tracks[7][i], bone_tracks[8][i]))
		motion_data[bone_id] = [
			pos_frames,
			rot_frames,
			scale_frames,
		]

if __name__ == "__main__":
	if len(sys.argv) <= 1:
		raise "No input file is provided!"
	for filepath in util.iter_path(sys.argv[1]):
		parse_file(filepath)