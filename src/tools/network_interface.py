'''
Created on Jan 13, 2014

@author: Vincent Ketelaars
'''

class Interface(object):
    def __init__(self, name, address, netmask, broadcast):
        self.name = name
        self.address = address # ip string
        self.netmask = netmask # ip string
        self.broadcast = broadcast # ip string
        self.gateway = None # ip string
        self.device = name[:-1] # Initialize to the interface name
        
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