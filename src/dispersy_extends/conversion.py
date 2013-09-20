'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''

import struct

from dispersy.conversion import BinaryConversion
from dispersy.conversion import DropPacket
from dispersy.logger import get_logger

from src.definitions import SEPARATOR, SIMPLE_MESSAGE_NAME, FILE_HASH_MESSAGE_NAME

logger = get_logger(__name__)

class SimpleFileConversion(BinaryConversion):
    '''
    classdocs
    '''    

    def __init__(self, community):
        '''
        Constructor
        '''
        super(SimpleFileConversion, self).__init__(community, "\x12")
        self.define_meta_message(chr(12), community.get_meta_message(SIMPLE_MESSAGE_NAME), self.encode_payload, self.decode_payload)
        
    def encode_payload(self, message):
        return struct.pack("!L", len(message.payload.filename + SEPARATOR + message.payload.data)), \
            message.payload.filename + SEPARATOR + message.payload.data

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
    
    def __init__(self, community):
        '''
        Constructor
        '''
        super(FileHashConversion, self).__init__(community, "\x13")
        self.define_meta_message(chr(13), community.get_meta_message(FILE_HASH_MESSAGE_NAME), self.encode_payload, self.decode_payload)
        
    def encode_payload(self, message):
        m = message.payload.filename + SEPARATOR + message.payload.directories + SEPARATOR + str(message.payload.roothash) + SEPARATOR + str(message.payload.address)
        return struct.pack("!L", len(m)), m

    def decode_payload(self, placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")
        data_length, = struct.unpack_from("!L", data, offset)
        offset += 4

        if len(data) < offset + data_length:
            raise DropPacket("Insufficient packet size")
        data_payload = data[offset:offset + data_length]
        file_offset = data_payload.find(SEPARATOR)
        filename = data_payload[0:file_offset]
        
        data_payload = data_payload[file_offset + len(SEPARATOR):]
        file_offset = data_payload.find(SEPARATOR)
        directories = data_payload[0:file_offset]
        
        data = data_payload[file_offset + len(SEPARATOR):]
        
        address_offset = data.find(SEPARATOR)
        roothash = data[:address_offset]        
        address_str = data[address_offset + len(SEPARATOR):]
        address = self._address_string_to_tuple(address_str)
        
        offset += data_length
        return offset, placeholder.meta.payload.implement(filename, directories, roothash, address)
    
    def _address_string_to_tuple(self, address_str):
        """
        Convert address string to tuple of ip and port
        
        @param address_str: Has form ('0.0.0.0', 12345) 
        """
        port_offset = address_str.find(",")
        ip = address_str[2:port_offset-1]
        port = int(address_str[port_offset+2:-1])
        return (ip, port)
        
        