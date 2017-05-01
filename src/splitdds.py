import os
import sys
import argparse
import util
import wta_parser

def split(infile, tex_hashes, out_dir):
	f = open(infile, "rb")
	data = f.read()
	f.close()
	
	infile_basename = os.path.basename(infile)
	outfile_basename_fmt = infile_basename.replace(".wtp", "_%d.dds")
	
	dds_list = data.split("DDS ")[1:]
	for i, dds in enumerate(dds_list):
		if i < len(tex_hashes):
			tex_hash = tex_hashes[i]
			filename = "%08X.dds" % tex_hash
		else:
			filename = outfile_basename_fmt % i
		outpath = os.path.join(out_dir, filename)
		
		if os.path.exists(outpath):
			continue
		
		fout = open(outpath, "wb")
		fout.write("DDS " + dds)
		fout.close()

def test(path):
	for fpath in util.iter_path(path):
		if fpath.endswith(".wtp"):
			print "processing:", fpath
			split(fpath)
			
if __name__ == '__main__':
	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument("--wtp", action="store", dest="wtp_path", type=str, required=True)
	arg_parser.add_argument("--wta", action="store", dest="wta_path", type=str)
	arg_parser.add_argument("--out_dir", action="store", dest="out_dir", type=str)
	args = arg_parser.parse_args()
	
	if args.wta_path:
		fp = open(args.wta_path, "rb")
		wta_reader = util.get_getter(fp, "<")
		wta = wta_parser.parse(wta_reader)
		fp.close()
		tex_hashes = wta.texture_hashes
		print tex_hashes
	else:
		tex_hashes = []
		
	if args.out_dir:
		out_dir = args.out_dir
	else:
		out_dir = os.path.split(args.wtp_path)[0]
		
	split(args.wtp_path, tex_hashes, out_dir)