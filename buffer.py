import struct

class Buffer:
    def __init__(self, data=bytes()):
        self.buffer = data
    
    def write(self, data):
        self.buffer += data
        return self
    
    def read(self, length=1):
        data = self.buffer[:length]
        self.buffer = self.buffer[length:]
        return data
    
    def writeInt8(self, data):
        self.write(bytes([data & 0xFF]))
        return self
    
    def readInt8(self):
        return ord(self.read())
    
    def writeInt16(self, data):
        self.write(bytes([(data >> 8) & 0xFF, (data >> 0) & 0xFF]))
        return self
    
    def readInt16(self):
        return self.readInt8() << 8 | self.readInt8() << 0
    
    def writeInt24(self, data):
        self.write(bytes([(data >> 16) & 0xFF, (data >> 8) & 0xFF, (data >> 0) & 0xFF]))
        return self
    
    def readInt24(self):
        return self.readInt8() << 16 | self.readInt8() << 8 | self.readInt8() << 0
    
    def writeInt32(self, data):
        self.write(bytes([(data >> 24) & 0xFF, (data >> 16) & 0xFF, (data >> 8) & 0xFF, (data >> 0) & 0xFF]))
        return self
    
    def readInt32(self):
        return self.readInt8() << 24 | self.readInt8() << 16 | self.readInt8() << 8 | self.readInt8() << 0

    def writeBool(self, data):
        self.write(chr(1 if data else 0))
        return self
    
    def readBool(self):
        return ord(self.read()) == 1
    
    def readFloat(self):
        data = struct.unpack("!f", self.buffer[:4])[0]
        self.buffer = self.buffer[4:]
        return data

    def writeFloat(self, data):
        self.write(struct.pack("!f", data))
        return self

    def readShor2(self):
        data = struct.unpack("<hh", self.buffer[:4][::-1])
        self.buffer = self.buffer[4:]
        return data

    def writeShor2(self, _1, _2):
        self.write(struct.pack("<hh", int(_1), int(_2))[::-1])
        return self

    def readVec2(self):
        data = struct.unpack("!ff", self.buffer[:8])
        self.buffer = self.buffer[8:]
        return data

    def writeVec2(self, _1, _2):
        self.write(struct.pack("!ff", _1, _2))
        return self
    
    def writeString(self, data):
        self.writeInt16(len(data))
        self.write(data)
        return self
    
    def readString(self):
        return self.read(self.readInt16())
    
    def writeBuffer(self, buffer):
        self.buffer += buffer
        return self

    def length(self):
        return len(self.buffer)
    
    def getLength(self):
        return self.length()
    
    def available(self):
        return self.length() > 0

    def toString(self):
        return self.buffer.decode('utf-8')
    
    def toBytes(self):
        return self.buffer
    
    def clear(self):
        self.buffer = ""
