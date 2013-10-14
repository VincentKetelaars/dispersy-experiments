'''
Created on Oct 14, 2013

@author: Vincent Ketelaars
'''

from socket import AF_INET, AF_INET6

class Address(object):
    '''
    This class represents an socket address. Either AF_INET or AF_INET6.
    '''

    def __init__(self, ip="0.0.0.0", port=0, family=AF_INET, flowinfo=0, scopeid=0):
        self._ip = ip
        self._port = port
        self._family = family
        self._flowinfo = flowinfo # IPv6 only
        self._scopeid = scopeid # IPv6 only
        
    @property
    def ip(self):
        return self._ip
    
    @property
    def port(self):
        return self._port
    
    @property
    def family(self):
        return self._family
    
    @classmethod
    def localport(cls, port_str):
        # Assumes basic IP family provided by init
        # All interfaces
        return cls(port=int(port_str))
        
    @classmethod
    def ipv4(cls, addr_str):
        # ip:port
        (ip, port) = cls.parse_ipv4_string(addr_str.strip())
        return cls(ip=ip, port=port, family=AF_INET)
        
    @classmethod
    def ipv6(cls, addr_str):
        # Use RFC2732
        # [ipv6]:port/flowinfo%scopeid
        (ip, port, flowinfo, scopeid) = cls.parse_ipv6_string(addr_str.strip())
        return cls(ip=ip, port=port, family=AF_INET6, flowinfo=flowinfo, scopeid=scopeid)
    
    @classmethod
    def unknown(cls, addr):
        if isinstance(addr, int):
            return cls(port=addr)
        addr = addr.strip()
        if addr.find(":") > 0:
            if addr.find("[") >= 0:
                return cls.ipv6(addr)
            else:
                return cls.ipv4(addr)
        else:
            return cls.localport(addr)
    
    @staticmethod
    def parse_ipv4_string(addr_str):
        split = addr_str.split(":")
        return (split[0], int(split[1]))
    
    @staticmethod
    def parse_ipv6_string(addr_str):
        scopeid = 0
        sp0 = addr_str.rsplit("%", 1)
        if len(sp0) == 2:
            scopeid = int(sp0[1])
        flowinfo = 0
        sp1 = sp0[0].rsplit("/", 1)
        if len(sp1) == 2:
            flowinfo = int(sp1[1])
        sp2 = sp1[0].rsplit(":", 1)
        # Remove both "[" and "]"
        return (sp2[0][1:-1], int(sp2[1]), flowinfo, scopeid)
    
    def set_ipv4(self, ip):
        self._ip = ip
        self._family = AF_INET
        
    def addr(self):
        if self.family == AF_INET:
            return (self.ip, self.port)
        elif self.family == AF_INET6:
            return (self.ip, self.port, self._flowinfo, self._scopeid)
        
    def __str__(self):
        if self.family == AF_INET:
            return self.ip + ":" + str(self.port)
        elif self.family == AF_INET6:
            return "[" + self.ip + "]:" + str(self.port)
        
    def is_wildcard_ip(self):
        return self.ip == "0.0.0.0"
    
    def is_wildcard_port(self):
        return self.port == 0