'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''

import struct

from dispersy.conversion import BinaryConversion
from dispersy.conversion import DropPacket

import logging
logger = logging.getLogger()

class SimpleFileConversion(BinaryConversion):
    '''
    classdocs
    '''
    
    SEPARATOR = ";;"

    def __init__(self, community):
        '''
        Constructor
        '''
        super(SimpleFileConversion, self).__init__(community, "\x12")
        self.define_meta_message(chr(12), community.get_meta_message(community.SIMPLE_MESSAGE_NAME), self.encode_payload, self.decode_payload)
        
    def encode_payload(self, message):
        return struct.pack("!L", len(message.payload.filename + self.SEPARATOR + message.payload.data)), \
            message.payload.filename + self.SEPARATOR + message.payload.data

    def decode_payload(self, placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")
        data_length, = struct.unpack_from("!L", data, offset)
        offset += 4

        if len(data) < offset + data_length:
            raise DropPacket("Insufficient packet size")
        data_payload = data[offset:offset + data_length]
        file_offset = data_payload.find(";;")
        filename = data_payload[0:file_offset]
        data = data_payload[file_offset+2:]
        offset += data_length

        return offset, placeholder.meta.payload.implement(filename, data)
    
    
class FileHashConversion(BinaryConversion):
    
    SEPARATOR = ";;"
    
    def __init__(self, community):
        '''
        Constructor
        '''
        super(FileHashConversion, self).__init__(community, "\x13")
        self.define_meta_message(chr(13), community.get_meta_message(community.FILE_HASH_MESSAGE), self.encode_payload, self.decode_payload)
        
    def encode_payload(self, message):
        m = message.payload.filename + self.SEPARATOR + str(message.payload.hash) + self.SEPARATOR + str(message.payload.address)
        return struct.pack("!L", len(m)), m            

    def decode_payload(self, placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")
        data_length, = struct.unpack_from("!L", data, offset)
        offset += 4

        if len(data) < offset + data_length:
            raise DropPacket("Insufficient packet size")
        data_payload = data[offset:offset + data_length]
        file_offset = data_payload.find(self.SEPARATOR)
        filename = data_payload[0:file_offset]
        data = data_payload[file_offset+2:]
        address_offset = data_payload.find(self.SEPARATOR)
        hash = data[:address_offset+2]
        address_str = data[address_offset+4:]
        address = self._address_string_to_tuple(address_str)
        offset += data_length
        
        return offset, placeholder.meta.payload.implement(filename, hash, address)
    
    def _address_string_to_tuple(self, address_str):
        port_offset = address_str.find(",")
        ip = address_str[2:port_offset-1]
        port = address_str[port_offset+2:-1]
        return (ip, port)
        
        