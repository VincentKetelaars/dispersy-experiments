'''
Created on Feb 6, 2014

@author: Vincent Ketelaars
'''
import unittest
from datetime import datetime
from src.address import Address
from src.dispersy_contact import DispersyContact
from src.download import Peer
from src.tools.network_interface import Interface
from src.logger import get_logger
logger = get_logger(__name__)

class Test(unittest.TestCase):


    def setUp(self):
        self.main = Address("193.156.108.78", port=12345)
        self.dc = DispersyContact(self.main)

    def tearDown(self):
        pass


    def test_sent_received(self):
        addr = Address(ip="127.0.0.1")
        self.dc.rcvd(2, 425, addr)
        self.dc.rcvd(3, 334, addr)
        self.assertEqual(self.dc.num_rcvd(), 5)
        self.assertEqual(self.dc.total_rcvd(), 759)
        self.assertNotEqual(self.dc.last_contact(addr), datetime.min)
        
        self.dc.sent(2, 425, addr)
        self.dc.sent(3, 334, addr)
        self.assertEqual(self.dc.num_sent(), 5)
        self.assertEqual(self.dc.total_sent(), 759)
        self.assertSequenceEqual(self.dc.no_contact_since(), [self.main])
        
#     def test_reachability(self):
#         address1 = Address("127.3.2.5")
#         address1._if = Interface(None, address1.ip, "255.0.0.0", None)
#         addresses = [self.main, Address("127.0.0.1"), Address("88.23.123.2"), Address("192.168.23.21")]
#         self.dc.set_peer(Peer(addresses))
#         self.assertSequenceEqual([addresses[1]], self.dc.reachable_addresses)
#         
#         address2 = Address("23.52.21.34")
#         logger.debug([str(a) for a in self.dc.reachable_addresses])
#         self.assertItemsEqual([addresses[0], addresses[2]], self.dc.reachable_addresses)

if __name__ == "__main__":
    unittest.main()