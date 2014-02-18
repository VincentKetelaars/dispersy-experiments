'''
Created on Jan 13, 2014

@author: Vincent Ketelaars
'''
from socket import AF_INET, AF_INET6

class Interface(object):
    def __init__(self, name, address, netmask, broadcast, version=AF_INET):
        self.name = name
        self.address = address # ip string
        self.netmask = netmask # ip string
        self.broadcast = broadcast # ip string
        self.gateway = None # ip string
        self.device = name[:-1] if name is not None else None # Initialize to the interface name
        self._version = version
        
    def ipv4(self):
        return self._version == AF_INET
    
    def ipv6(self):
        return self._version == AF_INET6
        
    def __str__(self):
        return "Interface (%s, %s, %s, %s, %s, %s) " %(self.name, self.address, self.netmask, self.broadcast, 
                                                       self.gateway, self.device)
        
    def __eq__(self, other):
        if not isinstance(other, Interface):
            return False
        if (self.name == other.name and self.address == other.address and self.netmask == other.netmask and
            self.broadcast == other.broadcast):
            return True
        return False
    
    def __ne__(self, other):
        return not self.__eq__(other)