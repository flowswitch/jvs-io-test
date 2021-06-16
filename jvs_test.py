#!/usr/bin/python3
# JVS I/O board tester
from struct import pack, unpack
from time import time, sleep
import serial


def _StuffByte(val):
	if val==0xD0:
		return b'\xD0\xCF'
	if val==0xE0:
		return b'\xD0\xDF'
	return pack('B', val)


class JVSMaster:
	def __init__(self, port, dump=False):
		self.dump = dump
		self.com = serial.Serial(port=port, baudrate=115200, timeout=1)

	def send(self, addr, data=b''):
		pkt = b'\xE0'+_StuffByte(addr)+_StuffByte(len(data)+1)
		s = addr+len(data)+1
		for b in data:
			s += b
			pkt += _StuffByte(b)
		pkt += _StuffByte(s & 0xFF)
		if self.dump:
			print('>', pkt.hex().upper())
		self.com.write(pkt)


	def _get_byte(self):
		b = self.com.read(1)[0]
		if b==0xE0:
			return 0x1E0
		if b==0xD0:
			b = self.com.read(1)[0] + 1
		return b


	def recv(self):
		tmo = time() + 1
		while self.com.read(1)!=b'\xE0':
			if time()>tmo:
				print("STX timeout")
				return None
		data = b''
		addr = self._get_byte()
		ck = addr
		l = self._get_byte()
		ck += l
		if l==0:
			print("Invalid LEN")
			return None
		l -= 1
		for i in range(l):
			
			b = self._get_byte()
			if b==0x1E0:
				print("Unexpected ETX")
				return None
			data += pack('<B', b)
			ck += b
		ckp = self._get_byte()
		if self.dump:
			print('< %02X [%X] %s %02X' % (addr, l, data.hex(), ckp))
		if (ck & 0xFF)!=ckp:
			print("Checksum error!")
			return None
		return addr, data


def DoTest(port):
	port = JVSMaster(port)

	port.send(0xFF, b'\xF0') # Reset all

	addr = 1
	port.send(0xFF, pack('BB', 0xF1, addr)) # Assign address 01 to the last board in the chain (TODO: scan the chain)
	port.recv()

	port.send(addr, b'\x10') # Read ID
	da, rsp = port.recv()
	print("ID:", rsp[2:-1].decode('ascii'))
	
	port.send(addr, b'\x11') # Read command format version
	da, rsp = port.recv()
	ver = rsp[2]
	print("Cmd format v%d.%d" % (ver>>4, ver & 0xF))

	port.send(addr, b'\x12') # Read JVS version
	da, rsp = port.recv()
	ver = rsp[2]
	print("JVS v%d.%d" % (ver>>4, ver & 0xF))

	port.send(addr, b'\x13') # Read protocol version
	da, rsp = port.recv()
	ver = rsp[2]
	print("Protocol v%d.%d" % (ver>>4, ver & 0xF))

	port.send(addr, b'\x14') # Read features
	da, rsp = port.recv()
	feat = rsp[2:]
	n_players = 0
	n_switches = 0

	def PrintSwitches(f, a, b, c):
		print("Player switches: %d players x %d switches" % (a, b))

	def PrintCoinSlots(f, a, b, c):
		print("Coin slots: %d slots" % (a))

	def PrintAnalogInputs(f, a, b, c):
		print("Analog inputs: %d channels of %d bits" % (a, b))

	def PrintRotaryEncoders(f, a, b, c):
		print("Rotary encoders: %d channels" % (a))

	def PrintKeypad(f, a, b, c):
		print("Keypad")

	def PrintLightGuns(f, a, b, c):
		print("Light guns: X %d bits, Y %d bits, %d channels" % (a, b, c))

	def PrintDINs(f, a, b, c):
		print("DIN: %d channels" % ((a<<8) + b))

	def PrintDOUTs(f, a, b, c):
		print("DOUT: %d channels" % (a))

	f_handlers = { 1: PrintSwitches, 2: PrintCoinSlots, 3: PrintAnalogInputs, 
		4: PrintRotaryEncoders, 5: PrintKeypad, 6: PrintLightGuns, 7: PrintDINs,
		0x12: PrintDOUTs }
		
	while feat[0]:
		if feat[0] in f_handlers:
			f_handlers[feat[0]](feat[0], feat[1], feat[2], feat[3])
		else:
			print("%02X: %02X %02X %02X" % (feat[0], feat[1], feat[2], feat[3]))
		if feat[0]==1:
			n_players = feat[1]
			n_switches = feat[2]
		feat = feat[4:]

	print("-------------- INPUT TEST --------------")
	n_bytes = (n_switches+7)//8
	while True:
		port.send(addr, pack('BBB', 0x20, n_players, n_bytes))
		da, rsp = port.recv()
		print("\r %02X " % (rsp[2]), end='')
		for i in range(n_players):
			print(" P%d: " % (i+1), end="")
			for j in range(n_bytes):
				print(format(rsp[3+i*n_bytes+j], '08b'), end=" ")


if __name__=='__main__':
	DoTest('/dev/ttyUSB0')
