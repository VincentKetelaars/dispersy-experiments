'''
Created on Nov 20, 2013

@author: Vincent Ketelaars
'''
import unittest
import os

from threading import Event

from src.api import API
from src.tests.unit.definitions import DISPERSY_WORKDIR, FILES
from src.definitions import SWIFT_BINPATH
from src.address import Address

class TestAPI(unittest.TestCase):


    def setUp(self):
        workdir = DISPERSY_WORKDIR + "/temp"
        if not os.path.exists(workdir):
            os.makedirs(workdir)
        self.api1 = API((workdir, SWIFT_BINPATH))
        self.api2 = API((workdir, SWIFT_BINPATH))
        self.event = Event()


    def tearDown(self):
        self.api1.stop()
        self.api2.stop()


    def test_add_file_both(self):
        addr = Address(ip="127.0.0.1", port=12421)
        self.api1.start()
        self.api1.add_socket(addr)
        self.api2.start()
        self.api2.add_peer(addr)
        self.event.wait(1)
        self.api1.add_files([FILES[0]])
        self.api2.add_files([FILES[1]])
        self.event.wait(5)


if __name__ == "__main__":
    unittest.main()