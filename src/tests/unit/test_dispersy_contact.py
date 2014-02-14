'''
Created on Feb 6, 2014

@author: Vincent Ketelaars
'''
import unittest
from datetime import datetime
from src.address import Address
from src.dispersy_contact import DispersyContact
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

if __name__ == "__main__":
    unittest.main()