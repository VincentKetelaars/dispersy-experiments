'''
Created on Aug 8, 2013

@author: Vincent Ketelaars
'''
from os.path import basename

from dispersy.payload import Payload

class SmallFileCarrier():
    
    def __init__(self, filename, data):
        self._filename = filename
        self._data = data
        
    @property
    def filename(self):
        return self._filename

    @property
    def data(self):
        return self._data

class SmallFilePayload(Payload):
    '''
    classdocs
    '''

    class Implementation(Payload.Implementation):
        
        def __init__(self, meta, filename, data):
            super(Payload.Implementation, self).__init__(meta)
            self._filename = basename(filename)
            self._data = data
        
        @property
        def filename(self):
            return self._filename
        
        @property
        def data(self):
            return self._data
        
class FileHashCarrier():
    
    def __init__(self, filename, directories, roothash, size, timestamp, addresses):
        self._filename = filename
        if directories is None:
            self._directories = ""
        else:
            self._directories = directories
        self._roothash = roothash
        self._size = size
        self._timestamp = timestamp # Time in seconds since epoch
        self._addresses = addresses
        
    @property
    def filename(self):
        return self._filename
    
    @property
    def directories(self):
        return self._directories
    
    @property
    def roothash(self):
        return self._roothash

    @property
    def size(self):
        return self._size 
    
    @property
    def timestamp(self):
        return self._timestamp
    
    @property
    def addresses(self):
        return self._addresses
    
class FileHashPayload(Payload):
    
    class Implementation(Payload.Implementation):
        
        def __init__(self, meta, filename, directories, roothash, size, timestamp, addresses):
            super(Payload.Implementation, self).__init__(meta)
            self._filename = basename(filename)
            self._directories = directories
            self._roothash = roothash
            self._size = size
            self._timestamp = timestamp # Time in seconds since epoch
            self._addresses = addresses
        
        @property
        def filename(self):
            return self._filename
        
        @property
        def directories(self):
            return self._directories
        
        @property
        def roothash(self):
            return self._roothash
        
        @property
        def size(self):
            return self._size
        
        @property
        def timestamp(self):
            return self._timestamp

        @property
        def addresses(self):
            return self._addresses
        
class AddressesCarrier():
    
    def __init__(self, addresses):
        self._addresses = addresses
    
    @property
    def addresses(self):
        return self._addresses
    
class AddressesPayload(Payload):
    
    class Implementation(Payload.Implementation):
        
        def __init__(self, meta, id_addresses):
            super(Payload.Implementation, self).__init__(meta)
            self._id_addresses = id_addresses # (id, lan, wan)
            
        @property
        def ids(self):
            return [ia[0] for ia in self._id_addresses]
        
        @property
        def addresses(self):
            return [ia[1] for ia in self._id_addresses]
        
        @property
        def wan_addresses(self):
            return [ia[2] for ia in self._id_addresses]
        
        @property
        def id_addresses(self):
            return self._id_addresses
        
class AddressesRequestCarrier():
    
    def __init__(self):
        pass
    
class AddressesRequestPayload(Payload):
    
    class Implementation(Payload.Implementation):
        
        def __init__(self, meta, sender_lan, sender_wan, endpoint_id):
            super(Payload.Implementation, self).__init__(meta)
            self._sender_lan = sender_lan
            self._sender_wan = sender_wan
            self._endpoint_id = endpoint_id
            
        @property
        def sender_lan(self):
            return self._sender_lan
                    
        @property
        def sender_wan(self):
            return self._sender_wan
        
        @property
        def endpoint_id(self):
            return self._endpoint_id
        
class PunctureCarrier():
    
    def __init__(self):
        pass
    
class PuncturePayload(Payload):
    
    class Implementation(Payload.Implementation):
        
        def __init__(self, meta, sender_lan, sender_wan, sender_id, address_vote, endpoint_id):
            super(Payload.Implementation, self).__init__(meta)
            self._sender_lan = sender_lan
            self._sender_wan = sender_wan
            self._sender_id = sender_id
            self._address_vote = address_vote
            self._endpoint_id = endpoint_id
            
        @property
        def sender_lan(self):
            return self._sender_lan
                    
        @property
        def sender_wan(self):
            return self._sender_wan
        
        @property
        def sender_id(self):
            return self._sender_id
        
        @property
        def address_vote(self):
            return self._address_vote
        
        @property
        def endpoint_id(self):
            return self._endpoint_id
        
class PunctureResponseCarrier():
    
    def __init__(self):
        pass
    
class PunctureResponsePayload(Payload):
    
    class Implementation(Payload.Implementation):
        
        def __init__(self, meta, sender_lan, sender_wan, address_vote, endpoint_id):
            super(Payload.Implementation, self).__init__(meta)
            self._sender_lan = sender_lan
            self._sender_wan = sender_wan
            self._address_vote = address_vote
            self._endpoint_id = endpoint_id
            
        @property
        def sender_lan(self):
            return self._sender_lan
                    
        @property
        def sender_wan(self):
            return self._sender_wan
        
        @property
        def address_vote(self):
            return self._address_vote
        
        @property
        def endpoint_id(self):
            return self._endpoint_id
        
class APIMessageCarrier():
    
    def __init__(self, message, addresses=[]):
        self._message = message
        self._addresses = addresses
        
    @property
    def message(self):
        return self._message
    
    @property
    def addresses(self):
        return self._addresses

class APIMessagePayload(Payload):
    '''
    classdocs
    '''

    class Implementation(Payload.Implementation):
        
        def __init__(self, meta, message):
            super(Payload.Implementation, self).__init__(meta)
            self._message = message
        
        @property
        def message(self):
            return self._message