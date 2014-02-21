'''
Created on Jan 13, 2014

@author: Vincent Ketelaars
'''
from socket import AF_INET, AF_INET6

class Interface(object):
    def __init__(self, name, address, netmask, broadcast, version=AF_INET, device=None, gateway=None):
        self.name = name
        self.address = address # ip string
        self.netmask = netmask # ip string
        self.broadcast = broadcast # ip string
        self.gateway = gateway # ip string
        self.device = device if device is not None else (name[:-1] if name is not None else None) # Initialize to the interface name
        self._version = version
        
    @classmethod
    def copy(cls, interface):
        assert isinstance(interface, Interface)
        return Interface(interface.name, interface.address, interface.netmask, interface.broadcast, 
                         interface.version, interface.device, interface.gateway)
        
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