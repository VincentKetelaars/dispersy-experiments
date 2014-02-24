'''
Created on Jan 13, 2014

@author: Vincent Ketelaars
'''
import netifaces
from src.tools.network_interface import Interface, AF_INET, AF_INET6
from src.logger import get_logger
logger = get_logger(__name__)

def get_interface_addresses(version=AF_INET):
    """
    Yields Interface instances for each available AF_INET interface found.

    An Interface instance has the following properties:
    - name          (i.e. "eth0")
    - address       (i.e. "10.148.3.254")
    - netmask       (i.e. "255.255.255.0")
    - broadcast     (i.e. "10.148.3.255")
    """

    for interface in netifaces.interfaces():
        try:
            addresses = netifaces.ifaddresses(interface)
        except ValueError:
            # some interfaces are given that are invalid, we encountered one called ppp0
            yield Interface(interface, None, None, None)
        else:
            if version == AF_INET:
                for option in addresses.get(netifaces.AF_INET, []):
                    try:
                        yield Interface(interface, option.get("addr"), option.get("netmask"), option.get("broadcast"))
                    except TypeError:
                        # some interfaces have no netmask configured, causing a TypeError when
                        # trying to unpack _l_netmask
                        pass
            elif version == AF_INET6:
                for option in addresses.get(netifaces.AF_INET6, []):
                    try:
                        yield Interface(interface, option.get("addr").split("%")[0], option.get("netmask"), option.get("broadcast"), version=AF_INET6)
                    except TypeError:
                        # some interfaces have no netmask configured, causing a TypeError when
                        # trying to unpack _l_netmask
                        pass
            else:
                logger.warning("Unknown version %s", version)