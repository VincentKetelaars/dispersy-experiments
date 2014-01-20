'''
Created on Oct 3, 2013

@author: Vincent Ketelaars
'''

import os
            
class FakeDispersy(object):

    def __init__(self):
        self._lan_address = ("0.0.0.0", 0)
    
    @property
    def lan_address(self):
        return self._lan_address
    
class FakeSwift(object):
    
    def __init__(self, addresses):
        self.listenaddrs = addresses
        self.confirmedaddrs = addresses
        self.roothash2dl = {}
        
    def set_on_swift_restart_callback(self, callback):
        pass
    
    def set_on_tcp_connection_callback(self, callback):
        pass
    
    def set_on_sockaddr_info_callback(self, callback):
        pass
    
    def add_socket(self, address):
        self.listenaddrs.append(address)
        
    def start_cmd_connection(self):
        pass
    
    def add_download(self, d):
        pass
    
    def get_pid(self):
        return os.getpid()