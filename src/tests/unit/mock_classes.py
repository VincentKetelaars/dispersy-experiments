'''
Created on Oct 3, 2013

@author: Vincent Ketelaars
'''
            
class FakeDispersy(object):

    def __init__(self):
        self._lan_address = ("0.0.0.0", 0)
    
    @property
    def lan_address(self):
        return self._lan_address