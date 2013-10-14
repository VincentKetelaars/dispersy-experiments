'''
Created on Oct 14, 2013

@author: Vincent Ketelaars
'''
import unittest

from src.address import Address, AF_INET, AF_INET6

class TestAddress(unittest.TestCase):


    def test_unknown_port(self):
        addr = Address.unknown("1")
        self.assertEqual(addr.port, 1)
        self.assertEqual(addr.ip, "0.0.0.0")
        self.assertEqual(addr.family, AF_INET)
        
    def test_unknown_ipv4(self):
        addr = Address.unknown("1.0.1.0:1")
        self.assertEqual(addr.port, 1)
        self.assertEqual(addr.ip, "1.0.1.0")
        self.assertEqual(addr.family, AF_INET)
        
    def test_unknown_ipv6_flowinfo(self):
        addr = Address.unknown("[FEDC:BA98:7654:3210:FEDC:BA98:7654:3210]:1/2")
        self.assertEqual(addr.port, 1)
        self.assertEqual(addr.ip, "FEDC:BA98:7654:3210:FEDC:BA98:7654:3210")
        self.assertEqual(addr.family, AF_INET6)
        self.assertEqual(addr._flowinfo, 2)
        self.assertEqual(addr._scopeid, 0)
        
    def test_unknown_ipv6_scopeid(self):
        addr = Address.unknown("[FEDC:BA98:7654:3210:FEDC:BA98:7654:3210]:1%3")
        self.assertEqual(addr.port, 1)
        self.assertEqual(addr.ip, "FEDC:BA98:7654:3210:FEDC:BA98:7654:3210")
        self.assertEqual(addr.family, AF_INET6)
        self.assertEqual(addr._flowinfo, 0)
        self.assertEqual(addr._scopeid, 3)
        
    def test_unknown_ipv6_all(self):
        addr = Address.unknown("[FEDC:BA98:7654:3210:FEDC:BA98:7654:3210]:1/2%3")
        self.assertEqual(addr.port, 1)
        self.assertEqual(addr.ip, "FEDC:BA98:7654:3210:FEDC:BA98:7654:3210")
        self.assertEqual(addr.family, AF_INET6)
        self.assertEqual(addr._flowinfo, 2)
        self.assertEqual(addr._scopeid, 3)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()