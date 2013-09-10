'''
Created on Aug 8, 2013

@author: Vincent Ketelaars
'''

from dispersy.payload import Payload

class SimpleFileCarrier():
    
    def __init__(self, filename, data):
        self._filename = filename
        self._data = data
        
    @property
    def filename(self):
        return self._filename

    @property
    def data(self):
        return self._data

class SimpleFilePayload(Payload):
    '''
    classdocs
    '''

    class Implementation(Payload.Implementation):
        
        def __init__(self, meta, filename, data):
            super(Payload.Implementation, self).__init__(meta)
            self._filename = filename
            self._data = data
        
        @property
        def filename(self):
            return self._filename
        
        @property
        def data(self):
            return self._data
        
class FileHashCarrier():
    
    def __init__(self, filename, directories, roothash, address):
        self._filename = filename
        if directories is None:
            self._directories = ""
        else:
            self._directories = directories
        self._roothash = roothash
        self._address = address
        
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
    def address(self):
        return self._address   
    
class FileHashPayload(Payload):
    
    class Implementation(Payload.Implementation):
        
        def __init__(self, meta, filename, directories, roothash, address):
            super(Payload.Implementation, self).__init__(meta)
            self._filename = filename
            self._directories = directories
            self._roothash = roothash
            self._address = address
        
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
        def address(self):
            return self._address