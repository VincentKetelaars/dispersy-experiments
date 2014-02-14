'''
Created on Feb 14, 2014

@author: Vincent Ketelaars
'''
import unittest
from os import urandom

from src.address import Address
from src.peer import Peer


class Test(unittest.TestCase):


    def setUp(self):
        self.lan = Address(ip="213.23.212.22", port=123)
        self.wan = Address(ip="213.23.212.22", port=123)
        self.id = urandom(16)
        self.peer = Peer([self.lan], [self.wan], [self.id])

    def tearDown(self):
        pass

    def test_simple_properties(self):
        self.assertEqual(self.peer.get(self.id), (self.lan, self.wan))
        self.assertEqual(self.peer.lan_addresses, [self.lan])
        self.assertEqual(self.peer.wan_addresses, [self.wan])
        self.assertItemsEqual(self.peer.addresses, set([self.lan, self.wan]))
        self.assertEqual(self.peer.get_id(self.lan), self.id)
        self.assertEqual(self.peer.get_id(self.wan), self.id)
        
    def test_update_wan(self):
        new_wan = Address(ip="12.231.21.21", port=234)
        self.peer.update_wan(self.lan, new_wan)
        self.assertEqual(self.peer.wan_addresses, [new_wan])

if __name__ == "__main__":
    unittest.main()