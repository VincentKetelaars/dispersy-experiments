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
        
        def __init__(self, meta, addresses):
            super(Payload.Implementation, self).__init__(meta)
            self._addresses = addresses
        
        @property
        def addresses(self):
            return self._addresses
        
class PunctureCarrier():
    
    def __init__(self):
        pass
    
class PuncturePayload(Payload):
    
    class Implementation(Payload.Implementation):
        
        def __init__(self, meta):
            super(Payload.Implementation, self).__init__(meta)
        
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