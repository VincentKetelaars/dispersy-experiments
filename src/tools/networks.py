'''
Created on Jan 13, 2014

@author: Vincent Ketelaars
'''
import netifaces
from src.tools.network_interface import Interface

def get_interface_addresses():
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
            for option in addresses.get(netifaces.AF_INET, []):
                try:
                    yield Interface(interface, option.get("addr"), option.get("netmask"), option.get("broadcast"))

                except TypeError:
                    # some interfaces have no netmask configured, causing a TypeError when
                    # trying to unpack _l_netmask
                    pass