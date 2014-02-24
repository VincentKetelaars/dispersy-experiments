'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''

import struct

from src.logger import get_logger
from dispersy.conversion import BinaryConversion
from dispersy.conversion import DropPacket

from src.definitions import SEPARATOR, SMALL_FILE_MESSAGE_NAME, FILE_HASH_MESSAGE_NAME,\
    ADDRESSES_MESSAGE_NAME, API_MESSAGE_NAME, PUNCTURE_MESSAGE_NAME,\
    ADDRESSES_REQUEST_MESSAGE_NAME, PUNCTURE_RESPONSE_MESSAGE_NAME
from src.address import Address

logger = get_logger(__name__)

ENDPOINT_ID_ENCODING = "base-64"

class SmallFileConversion(BinaryConversion):
    '''
    classdocs
    '''    

    def __init__(self, community):
        super(SmallFileConversion, self).__init__(community, "\x12")
        self.define_meta_message(chr(12), community.get_meta_message(SMALL_FILE_MESSAGE_NAME), self.encode_payload, 
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
        m = str(message.payload.filename) + SEPARATOR + str(message.payload.directories) + SEPARATOR + \
            str(message.payload.roothash) + SEPARATOR + str(message.payload.size) + SEPARATOR + \
            str(message.payload.timestamp)
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
        size = long(data_pieces[3])
        timestamp = float(data_pieces[4])
        addresses = [Address.unknown(a) for a in data_pieces[5:]]
            
        offset += data_length
        
        return offset, placeholder.meta.payload.implement(filename, directories, roothash, size, timestamp, addresses)

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
        for _id, addr, wan in message.payload.id_addresses:
            m += _id.encode(ENDPOINT_ID_ENCODING) + SEPARATOR + str(addr) + SEPARATOR + str(wan) + SEPARATOR
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
        id_addrs = data_payload.split(SEPARATOR)
        id_addresses = zip([i.decode(ENDPOINT_ID_ENCODING) for i in id_addrs[0::3]], # id 
                           [Address.unknown(a) for a in id_addrs[1::3]], # lan
                           [Address.unknown(a) for a in id_addrs[2::3]]) # wan
        offset += data_length

        return offset, placeholder.meta.payload.implement(id_addresses)
    
class AddressesRequestConversion(BinaryConversion):
    '''
    classdocs
    '''    

    def __init__(self, community):
        super(AddressesRequestConversion, self).__init__(community, "\x17")
        self.define_meta_message(chr(17), community.get_meta_message(ADDRESSES_REQUEST_MESSAGE_NAME), self.encode_payload, 
                                 self.decode_payload)
        
    def encode_payload(self, message):
        m = str(message.payload.sender_lan) + SEPARATOR + str(message.payload.sender_wan) + SEPARATOR + \
            message.payload.endpoint_id.encode(ENDPOINT_ID_ENCODING) + SEPARATOR + str(message.payload.wan_address)
        return struct.pack("!L", len(m)), m

    def decode_payload(self, placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")
        data_length, = struct.unpack_from("!L", data, offset)
        offset += 4

        if len(data) < offset + data_length:
            raise DropPacket("Insufficient packet size")
        data_payload = data[offset:offset + data_length]
        splitted = data_payload.split(SEPARATOR)
        sender_lan = Address.unknown(splitted[0])
        sender_wan = Address.unknown(splitted[1])
        endpoint_id = splitted[2].decode(ENDPOINT_ID_ENCODING)
        wan_address = Address.unknown(splitted[3])
        offset += data_length

        return offset, placeholder.meta.payload.implement(sender_lan, sender_wan, endpoint_id, wan_address)
    
class PunctureConversion(BinaryConversion):
    '''
    classdocs
    '''    

    def __init__(self, community):
        super(PunctureConversion, self).__init__(community, "\x15")
        self.define_meta_message(chr(15), community.get_meta_message(PUNCTURE_MESSAGE_NAME), self.encode_payload, 
                                 self.decode_payload)
        
    def encode_payload(self, message):
        m = str(message.payload.sender_lan) + SEPARATOR + str(message.payload.sender_wan) + SEPARATOR + \
            message.payload.sender_id.encode(ENDPOINT_ID_ENCODING) + SEPARATOR + str(message.payload.address_vote) + SEPARATOR + \
            message.payload.endpoint_id.encode(ENDPOINT_ID_ENCODING)
        return struct.pack("!L", len(m)), m

    def decode_payload(self, placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")
        data_length, = struct.unpack_from("!L", data, offset)
        offset += 4

        if len(data) < offset + data_length:
            raise DropPacket("Insufficient packet size")
        data_payload = data[offset:offset + data_length]
        splitted = data_payload.split(SEPARATOR)
        sender_lan = Address.unknown(splitted[0])
        sender_wan = Address.unknown(splitted[1])
        sender_id = splitted[2].decode(ENDPOINT_ID_ENCODING)
        address_vote = Address.unknown(splitted[3])
        endpoint_id = splitted[4].decode(ENDPOINT_ID_ENCODING)
        offset += data_length

        return offset, placeholder.meta.payload.implement(sender_lan, sender_wan, sender_id, address_vote, endpoint_id)
    
class PunctureResponseConversion(BinaryConversion):
    '''
    classdocs
    '''    

    def __init__(self, community):
        super(PunctureResponseConversion, self).__init__(community, "\x18")
        self.define_meta_message(chr(18), community.get_meta_message(PUNCTURE_RESPONSE_MESSAGE_NAME), self.encode_payload, 
                                 self.decode_payload)
        
    def encode_payload(self, message):
        m = str(message.payload.sender_lan) + SEPARATOR + str(message.payload.sender_wan) + SEPARATOR + \
            str(message.payload.address_vote) + SEPARATOR + message.payload.endpoint_id.encode(ENDPOINT_ID_ENCODING)
        return struct.pack("!L", len(m)), m

    def decode_payload(self, placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")
        data_length, = struct.unpack_from("!L", data, offset)
        offset += 4

        if len(data) < offset + data_length:
            raise DropPacket("Insufficient packet size")
        data_payload = data[offset:offset + data_length]
        splitted = data_payload.split(SEPARATOR)
        sender_lan = Address.unknown(splitted[0])
        sender_wan = Address.unknown(splitted[1])
        address_vote = Address.unknown(splitted[2])
        endpoint_id = splitted[3].decode(ENDPOINT_ID_ENCODING)
        offset += data_length

        return offset, placeholder.meta.payload.implement(sender_lan, sender_wan, address_vote, endpoint_id)
    
class APIMessageConversion(BinaryConversion):
    '''
    classdocs
    '''    

    def __init__(self, community):
        super(APIMessageConversion, self).__init__(community, "\x16")
        self.define_meta_message(chr(16), community.get_meta_message(API_MESSAGE_NAME), self.encode_payload, 
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
        