'''
Created on Nov 20, 2013

@author: Vincent Ketelaars
'''
import unittest
import os
from threading import Event

from src.logger import get_logger

from src.api import API
from src.tests.unit.definitions import DISPERSY_WORKDIR, FILES
from src.definitions import SWIFT_BINPATH, TIMEOUT_TESTS
from src.address import Address
from src.tests.unit.test_endpoint import remove_files

logger = get_logger(__name__)

class TestAPI(unittest.TestCase):


    def setUp(self):
        self.workdir = DISPERSY_WORKDIR + "/temp"
        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)
        self.api1 = API(*(self.workdir, SWIFT_BINPATH),**{"walker":False})
        self.api2 = API(*(self.workdir, SWIFT_BINPATH),**{"walker":False})
        self.event = Event()
        self.files = FILES
        self.files_to_remove = []


    def tearDown(self):
        self.api1.stop()
        self.api2.stop()
        for f in self.files_to_remove:
            remove_files(f, True)
        

    def test_add_file_both(self):
        addr = Address(ip="127.0.0.1", port=12421)
        self.api1.start()
        self.api1.add_socket(addr.ip, addr.port, addr.family)
        self.api2.start()
        self.api2.add_peer(addr.ip, addr.port, addr.family)
        
        self.files_done = 0
        def callback(file_):
            self.files_done += 1
            if self.files_done == 2:
                self.event.set()

        self.api1.file_received_callback(callback)
        self.api2.file_received_callback(callback)
        
        self.api1.add_file(self.files[0])
        self.api2.add_file(self.files[1])
        file0 = os.path.join(self.workdir, os.path.basename(self.files[0]))
        file1 = os.path.join(self.workdir, os.path.basename(self.files[1]))
        self.files_to_remove.append(file0)
        self.files_to_remove.append(file1)
        self.event.wait(TIMEOUT_TESTS)
        
        self.assertTrue(os.path.exists(file0))
        self.assertTrue(os.path.exists(file1))
        
    def test_add_socket_if_came_up_and_process_unstarted(self):
        address = Address(ip="127.0.0.1", port=12345)
        
        self.fails = 0
        def callback(addr, errno):
            logger.debug("Adding address failed %s %d", addr, errno)
            self.fails += 1
            self.event.set()
        
        self.api1.socket_error_callback(callback)
        self.api1.add_socket(address.ip, address.port, address.family)
        self.api1.interface_came_up(address.ip, "lo", "lo", gateway="127.0.0.1")
        self.api1.start()
        
        self.event.wait(2) # Should be plenty of time
        self.assertEqual(self.fails, 0)


if __name__ == "__main__":
    unittest.main()