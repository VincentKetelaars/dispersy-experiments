'''
Created on Aug 8, 2013

@author: Vincent Ketelaars
'''

from dispersy.payload import Payload

class MyPayload(Payload):
    '''
    classdocs
    '''


    class Implementation(Payload.Implementation):
        
        def __init__(self, meta, data):
            super(Payload.Implementation, self).__init__(meta)
            self.data = data