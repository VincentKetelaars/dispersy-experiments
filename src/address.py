'''
Created on Oct 14, 2013

@author: Vincent Ketelaars
'''
from struct import unpack
from socket import AF_INET, AF_INET6, inet_aton

from src.tools.networks import get_interface_addresses

from src.logger import get_logger
from src.tools.network_interface import Interface
logger = get_logger(__name__)

class Address(object):
    '''
    This class represents an socket address. Either AF_INET or AF_INET6.
    '''
    
    IFNAME_WILDCARD= "All"

    def __init__(self, ip="0.0.0.0", port=0, family=AF_INET, flowinfo=0, scopeid=0, interface=None):
        self._ip = ip
        self._port = port
        self._family = family
        self._flowinfo = flowinfo # IPv6 only
        self._scopeid = scopeid # IPv6 only
        self._if = interface
        
    @property
    def ip(self):
        return self._ip
    
    @property
    def port(self):
        return self._port
    
    @property
    def family(self):
        return self._family
    
    @property
    def flowinfo(self):
        return self._flowinfo
    
    @property
    def scopeid(self):
        return self._scopeid
    
    @property
    def interface(self):
        return self._if
    
    @classmethod
    def copy(cls, addr):
        # Assume Address instance
        try:
            return cls(ip=addr.ip, port=addr.port, family=addr.family, flowinfo=addr.flowinfo, scopeid=addr.scopeid, 
                       interface=addr.interface)
        except:
            logger.debug("Not an Address instance!")
            return cls()
    
    @classmethod
    def localport(cls, port_str):
        # Assumes basic IP family provided by init
        # All interfaces
        try:
            port = int(port_str)
            return cls(port=port)
        except:
            logger.debug("Not a number format! Fall back to default")
            return cls()
        
    @classmethod
    def ipv4(cls, addr_str):
        # ip:port
        try:
            (ip, port) = cls.parse_ipv4_string(addr_str.strip())
            return cls(ip=ip, port=port, family=AF_INET)
        except:
            logger.debug("Not an ipv4 format! Fall back to default")
            return cls()
        
    @classmethod
    def ipv6(cls, addr_str):
        # Use RFC2732
        # [ipv6]:port/flowinfo%scopeid
        try:
            (ip, port, flowinfo, scopeid) = cls.parse_ipv6_string(addr_str.strip())
            return cls(ip=ip, port=port, family=AF_INET6, flowinfo=flowinfo, scopeid=scopeid)
        except:
            logger.debug("Not an ipv6 format! Fall back to default ipv6")
            return cls(ip="::0", family=AF_INET6)
    
    @classmethod
    def unknown(cls, addr):
        addr = addr.strip()
        if isinstance(addr, Address):
            cls.copy(addr)
        try:
            p = int(addr)
            # If it is an integer, it is a port
            return cls(port=p)
        except:
            pass
        if len(addr) == 2:
            return cls.tuple(addr)
        # Not an integer or tuple, so most likely a string
        try:               
            if addr.find(":") > 0:
                if addr.find("[") >= 0:
                    return cls.ipv6(addr)
                else:
                    return cls.ipv4(addr)
            else:
                # Assume ipv4
                return cls.ipv4(addr)
        except:
            logger.debug("Unknown address format! Fall back to default")
            cls()
            
    @classmethod
    def tuple(cls, tuple_addr):
        try:
            if tuple_addr[0].find("[") == 0:
                return cls.ipv6(tuple_addr[0] + ":" + str(tuple_addr[1]))
            else:
                return cls.ipv4(tuple_addr[0] + ":" + str(tuple_addr[1]))
        except:
            logger.exception("Irregular tuple! Fall back to default")
            return cls()
    
    @staticmethod
    def parse_ipv4_string(addr_str):
        sp = addr_str.split(":")
        port = 0
        if len(sp) == 2:
            port = int(sp[1])
        return (sp[0], port)
    
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
        if (sp1[0].endswith("]")):
            return (sp1[0][1:-1], 0, flowinfo, scopeid)
        sp2 = sp1[0].rsplit(":", 1)
        # Remove both "[" and "]"
        return (sp2[0][1:-1], int(sp2[1]), flowinfo, scopeid)
    
    def set_ipv4(self, ip):
        self._ip = ip
        self._family = AF_INET
        
    def set_port(self, port):
        self._port = port
        
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
    
    def resolve_interface(self):
        if self.interface_exists():
            return True
        if self.is_wildcard_ip():
            self._if = Interface(self.IFNAME_WILDCARD, self._ip, self._ip, self._ip)
            return True
        try:
            for if_ in get_interface_addresses():            
                if (self.ipstr_to_int(if_.address) & self.ipstr_to_int(if_.netmask) == 
                    self.ipstr_to_int(self._ip) & self.ipstr_to_int(if_.netmask)): # Same subnet
                    self._if = Interface(if_.name, if_.address, if_.netmask, if_.broadcast)
                    return True
        except:
            logger.exception("Failed to find %s", self._ip)
        return False
    
    def interface_exists(self):
        if self._if is None:
            return False
        for if_ in get_interface_addresses():
            if (self._if.name == if_.name and self._if.address == if_.address):
                return True
        return False
    
    def ipstr_to_int(self, address):
        return unpack("!L", inet_aton(address))[0]
    
    def __eq__(self, other):
        if not isinstance(other, Address):
            return False
        if (self._ip == other._ip and self._port == other._port and self._family == other._family and 
            self._flowinfo == other._flowinfo and self._scopeid == other._scopeid):
            return True
        return False
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def __hash__(self):
        return hash((self._ip, self._port, self._family, self._flowinfo, self._scopeid))
