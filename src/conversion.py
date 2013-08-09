'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''

import struct

from dispersy.conversion import BinaryConversion
from dispersy.conversion import DropPacket

class MyConversion(BinaryConversion):
    '''
    classdocs
    '''


    def __init__(self, community):
        '''
        Constructor
        '''
        super(MyConversion, self).__init__(community, "\x12")
        self.define_meta_message(chr(12), community.get_meta_message(u"mymessage"), self.encode_payload, self.decode_payload)
        
    def encode_payload(self, message):
        return struct.pack("!L", len(message.payload.data)), message.payload.data

    def decode_payload(self, placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")
        data_length, = struct.unpack_from("!L", data, offset)
        offset += 4

        if len(data) < offset + data_length:
            raise DropPacket("Insufficient packet size")
        data_payload = data[offset:offset + data_length]
        offset += data_length

        return offset, placeholder.meta.payload.implement(data_payload)