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
        addr = Address.unknown("12")
        self.assertEqual(addr.port, 12)
        self.assertEqual(addr.ip, "0.0.0.0")
        self.assertEqual(addr.family, AF_INET)
        addr = Address.unknown(" 12 ")
        self.assertEqual(addr.port, 12)
        self.assertEqual(addr.ip, "0.0.0.0")
        self.assertEqual(addr.family, AF_INET)
        
    def test_no_port_ipv4(self):
        addr = Address.ipv4("0.0.0.0")
        self.assertEqual(addr.port, 0)
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
        
    def test_no_port_ipv6(self):
        addr = Address.unknown("[::0]")
        self.assertEqual(addr.port, 0)
        self.assertEqual(addr.ip, "::0")
        self.assertEqual(addr.family, AF_INET6)
        
    def test_address_equal(self):
        self.assertEqual(Address(port=1234), Address(port=1234))
        self.assertEqual(Address(ip="0.0.1.2", port=1234), Address(ip="0.0.1.2", port=1234))
        self.assertEqual(Address("::3", 12321, AF_INET6, 1, 1), Address("::3", 12321, AF_INET6, 1, 1))
        
    def test_resolve_interface(self):
        addr = Address.unknown("127.0.0.1:1")
        addr.resolve_interface()
        self.assertEqual(addr.interface.name, "lo")
        
    def test_private_address(self):
        addr = Address(ip="127.2.3.1")
        self.assertTrue(addr.is_private_address())
        addr = Address(ip="10.12.124.231")
        self.assertTrue(addr.is_private_address())
        addr = Address(ip="192.168.124.231")
        self.assertTrue(addr.is_private_address())
        addr = Address(ip="172.28.124.231")
        self.assertTrue(addr.is_private_address())
        addr = Address(ip="192.180.124.231")
        self.assertFalse(addr.is_private_address())
        
    def test_tuple(self):
        addr = Address.unknown(("1.0.1.0", 1)) # int as port
        self.assertEqual(addr.port, 1)
        self.assertEqual(addr.ip, "1.0.1.0")
        self.assertEqual(addr.family, AF_INET)
        addr = Address.unknown(("[FEDC:BA98:7654:3210:FEDC:BA98:7654:3210]", "1")) # string as port
        self.assertEqual(addr.port, 1)
        self.assertEqual(addr.ip, "FEDC:BA98:7654:3210:FEDC:BA98:7654:3210")
        self.assertEqual(addr.family, AF_INET6)
        self.assertEqual(addr._flowinfo, 0)
        self.assertEqual(addr._scopeid, 0)

if __name__ == "__main__":
    unittest.main()