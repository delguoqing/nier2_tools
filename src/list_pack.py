import sys
import dat_unpack

if __name__ == '__main__':
	fp = open(sys.argv[1], "rb")
	data = fp.read()
	fp.close()
	dat_unpack.unpack(data)