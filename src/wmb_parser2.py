import util
import sys
import argparse

from fmt_def.nier2 import wmb_fmt
from fmt_def.core import ReadContext

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description="Nier2: Automata model tool.")
	#parser.add_argument("cmd", help="command you want to perform", choices=["parse", "mod"])
	parser.add_argument("--wmb", action="store", dest="in_path", type=str, help="Input file(s). A file or a directory.")
	#parser.add_argument("--random", action="store_true", default=False)
	#parser.add_argument("--dry_run", action="store_true", default=False)
	#parser.add_argument("--format", action="store", type=str, choices=["gtb", "obj"], default="gtb")
	#parser.add_argument("--meshes", action="store", type=int, nargs="*", help="Indices of meshes that will be replaced")
	#parser.add_argument("--mesh_reps", action="store", type=str, nargs="*", help="json files which is the replacement of meshes.")
	
	args = parser.parse_args()
	
	f = open(args.in_path, "rb")
	f = util.get_getter(f, "<")
	
	wmb3 = wmb_fmt.getFormat()
	wmb3.read(f, ReadContext(0, "<"))
	print(wmb3.pretty_print(maxArraySize=200))