'''
Created on Oct 3, 2013

@author: Vincent Ketelaars
'''

import os
from src.swift.swift_process import MySwiftProcess
            
class FakeDispersy(object):

    def __init__(self):
        self._lan_address = ("0.0.0.0", 0)
    
    @property
    def lan_address(self):
        return self._lan_address
    
class FakeSwift(MySwiftProcess):
    
    def __init__(self, addresses):
        self.working_sockets = set(addresses)
        self.roothash2dl = {}
    
    def add_socket(self, address):
        self.working_sockets.add(address)
        
    def start_cmd_connection(self):
        pass
    
    def add_download(self, d):
        pass
    
    def get_pid(self):
        return os.getpid()