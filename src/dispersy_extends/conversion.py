'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''

import struct

from src.logger import get_logger
from dispersy.conversion import BinaryConversion
from dispersy.conversion import DropPacket

from src.definitions import SEPARATOR, SIMPLE_MESSAGE_NAME, FILE_HASH_MESSAGE_NAME,\
    ADDRESSES_MESSAGE_NAME, API_MESSAGE_NAME
from src.address import Address

logger = get_logger(__name__)

class SimpleFileConversion(BinaryConversion):
    '''
    classdocs
    '''    

    def __init__(self, community):
        super(SimpleFileConversion, self).__init__(community, "\x12")
        self.define_meta_message(chr(12), community.get_meta_message(SIMPLE_MESSAGE_NAME), self.encode_payload, 
                                 self.decode_payload)
        
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
        data_pieces = data_payload.split(SEPARATOR)
        filename = data_pieces[0]
        data = data_pieces[1]
        offset += data_length

        return offset, placeholder.meta.payload.implement(filename, data)
    
    
class FileHashConversion(BinaryConversion):
    
    def __init__(self, community):
        super(FileHashConversion, self).__init__(community, "\x13")
        self.define_meta_message(chr(13), community.get_meta_message(FILE_HASH_MESSAGE_NAME), self.encode_payload, 
                                 self.decode_payload)
        
    def encode_payload(self, message):
        m = str(message.payload.filename) + SEPARATOR + str(message.payload.directories) + SEPARATOR + str(message.payload.roothash)
        for addr in message.payload.addresses:
            m += SEPARATOR + str(addr)
        return struct.pack("!L", len(m)), m

    def decode_payload(self, placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")
        data_length, = struct.unpack_from("!L", data, offset)
        offset += 4

        if len(data) < offset + data_length:
            raise DropPacket("Insufficient packet size")
        data_payload = data[offset:offset + data_length]
        data_pieces = data_payload.split(SEPARATOR)
        filename = data_pieces[0]
        directories = data_pieces[1]
        roothash = data_pieces[2]
        addresses = [Address.unknown(a) for a in data_pieces[3:]]
            
        offset += data_length
        
        return offset, placeholder.meta.payload.implement(filename, directories, roothash, addresses)

class AddressesConversion(BinaryConversion):
    '''
    classdocs
    '''    

    def __init__(self, community):
        super(AddressesConversion, self).__init__(community, "\x14")
        self.define_meta_message(chr(14), community.get_meta_message(ADDRESSES_MESSAGE_NAME), self.encode_payload, 
                                 self.decode_payload)
        
    def encode_payload(self, message):
        m = ""
        for addr in message.payload.addresses:
            m += str(addr) + SEPARATOR
        m = m[:-len(SEPARATOR)]
        return struct.pack("!L", len(m)), m

    def decode_payload(self, placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")
        data_length, = struct.unpack_from("!L", data, offset)
        offset += 4

        if len(data) < offset + data_length:
            raise DropPacket("Insufficient packet size")
        data_payload = data[offset:offset + data_length]
        address_strs = data_payload.split(SEPARATOR)
        addresses = [Address.unknown(a) for a in address_strs]
        offset += data_length

        return offset, placeholder.meta.payload.implement(addresses)
    
class APIMessageConversion(BinaryConversion):
    '''
    classdocs
    '''    

    def __init__(self, community):
        super(APIMessageConversion, self).__init__(community, "\x15")
        self.define_meta_message(chr(15), community.get_meta_message(API_MESSAGE_NAME), self.encode_payload, 
                                 self.decode_payload)
        
    def encode_payload(self, message):
        return struct.pack("!L", len(message.payload.message)), message.payload.message

    def decode_payload(self, placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")
        data_length, = struct.unpack_from("!L", data, offset)
        offset += 4

        if len(data) < offset + data_length:
            raise DropPacket("Insufficient packet size")
        message = data[offset:offset + data_length]
        offset += data_length

        return offset, placeholder.meta.payload.implement(message)
        