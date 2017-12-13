import sys
import struct

DST_PATH = r"D:\Program Files (x86)\Steam\steamapps\common\NieRAutomata\data\pl\pl0000.dtt"
SRC_PATH = r"D:\Program Files (x86)\Steam\steamapps\common\NieRAutomata\data\pl\pl0000.BAK"

def replace(wmb_path):
	f = open(wmb_path, "rb")
	data = f.read()
	f.close()
	
	fbase = open(SRC_PATH, "rb")
	database = fbase.read()
	fbase.close()
	
	result = database[:0x50] + struct.pack("<I", len(data)) + database[0x54: 0xdd1bc0] + data
	
	fout = open(DST_PATH, "wb")
	fout.write(result)
	fout.close()
	
if __name__ == '__main__':
	replace(sys.argv[1])