'''
Created on Aug 8, 2013

@author: Vincent Ketelaars
'''

from dispersy.payload import Payload

class SimpleFileCarrier():
    
    def __init__(self, data, filename):
        self._data = data
        self._filename = filename
        
    @property
    def data(self):
        return self._data
    
    @property
    def filename(self):
        return self._filename

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
        def data(self):
            return self._data
        
        @property
        def filename(self):
            return self._filename