'''
Created on Nov 15, 2013

@author: Vincent Ketelaars
'''
import unittest
import random
import socket

from src.logger import get_logger

from src.address import Address
from src.dispersy_instance import verify_addresses_are_free
from src.definitions import RANDOM_PORTS
from src.tools.networks import get_interface_addresses


logger = get_logger(__name__)

class TestVerifyAddresses(unittest.TestCase):

    def test_free_wildcard_addresses(self):
        self.addresses = [Address(port=12642), Address(port=4783)]
        addresses = verify_addresses_are_free(self.addresses[:])
        for addr in addresses:
            self.assertTrue(addr in self.addresses)
            
    def test_occupied_address(self):
        interfaces = get_interface_addresses()
        self.addresses = []
        for i in interfaces: # AF_INET only
            addr = Address(ip=i.address, port=random.randint(*RANDOM_PORTS))
            self.addresses.append(addr)
            s = socket.socket(addr.family, socket.SOCK_DGRAM)
            s.bind(addr.addr())
        
        logger.debug("Created addresses %s", " ".join(map(str, self.addresses)))
        addresses = verify_addresses_are_free(self.addresses[:])
        for addr in addresses:
            self.assertIn(addr.ip, [addr.ip for addr in self.addresses])

if __name__ == "__main__":
    unittest.main()