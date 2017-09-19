import os
import sys
import util
import numpy
import wmb_parser
import wta_parser
import splitdds

def handle_wmb(fpath, out_dir):
	fp = open(fpath, "rb")
	wmb = util.get_getter(fp, "<")
	wmb = wmb_parser.parse(wmb)
	fp.close()
	
	wmb_parser.dump_wmb(
		wmb,
		outpath=os.path.join(out_dir,
							 os.path.split(fpath)[1].replace(".wmb", ".gtb"))
	)
		
def handle_dds(wtp_path, wta_path, out_dir):
	if wta_path:
		fp = open(wta_path, "rb")
		wta_reader = util.get_getter(fp, "<")
		wta = wta_parser.parse(wta_reader)
		fp.close()
		tex_hashes = wta.texture_hashes
		print tex_hashes
	else:
		tex_hashes = []		
	splitdds.split(wtp_path, tex_hashes, out_dir)
	
if __name__ == '__main__':
	wta_path = wtp_path = wmb_path = None
	for arg in sys.argv:
		if arg.endswith(".wta"):
			wta_path = arg
		elif arg.endswith(".wtp"):
			wtp_path = arg
		elif arg.endswith(".wmb"):
			wmb_path = arg
			
	out_dir = os.path.split(sys.argv[0])[0]
	
	if wmb_path is not None:
		handle_wmb(wmb_path, out_dir)
		
	if wtp_path is not None:
		handle_dds(wtp_path, wta_path, out_dir)