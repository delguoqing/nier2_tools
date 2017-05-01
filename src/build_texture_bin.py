import os
import sys
import splitdds
import wta_parser
import util

if __name__ == "__main__":
	in_root_dir = sys.argv[1]
	out_dir = sys.argv[2]
	for path in util.iter_path(sys.argv[1]):
		if path.endswith(".wta"):
			print "processing %s" % os.path.basename(path)
			print path
			wtp_path = path.replace("_dat_unpacked", "_dtt_unpacked").replace(".wta", ".wtp")
			
			fp = open(path, "rb")
			wta_reader = util.get_getter(fp, "<")
			wta = wta_parser.parse(wta_reader)
			fp.close()
			
			try:
				splitdds.split(wtp_path, wta.texture_hashes, out_dir)
			except IOError:
				print >>sys.stderr, "IOError on %s" % wtp_path