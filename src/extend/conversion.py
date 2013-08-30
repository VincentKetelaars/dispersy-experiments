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
        self.define_meta_message(chr(12), community.get_meta_message(community.MESSAGE_NAME), self.encode_payload, self.decode_payload)
        
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