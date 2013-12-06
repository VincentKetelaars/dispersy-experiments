'''
Created on Nov 20, 2013

@author: Vincent Ketelaars
'''
import unittest
import os
import re
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
        self.api1 = API("API1", self.workdir, SWIFT_BINPATH, walker=False)
        self._run_event = Event()
        self.files = FILES
        self.files_to_remove = []


    def tearDown(self):
        self.api1.stop()
        for f in self.files_to_remove:
            remove_files(f, True)
        

    def test_add_file_both(self):
        self.api2 = API("API2", self.workdir, SWIFT_BINPATH, walker=False)        
        
        addr = Address(ip="127.0.0.1", port=12421)
        self.api1.start()
        self.api1.add_socket(addr.ip, addr.port, addr.family)
        self.api2.start()
        self.api2.add_peer(addr.ip, addr.port, addr.family)
        
        self.files_done = 0
        def callback(file_):
            self.files_done += 1
            if self.files_done == 2:
                self._run_event.set()

        self.api1.file_received_callback(callback)
        self.api2.file_received_callback(callback)
        
        self.api1.add_file(self.files[0])
        self.api2.add_file(self.files[1])
        file0 = os.path.join(self.workdir, os.path.basename(self.files[0]))
        file1 = os.path.join(self.workdir, os.path.basename(self.files[1]))
        self.files_to_remove.append(file0)
        self.files_to_remove.append(file1)
        self._run_event.wait(TIMEOUT_TESTS)
        
        self.assertTrue(os.path.exists(file0))
        self.assertTrue(os.path.exists(file1))
        
        self.api2.stop()
        
    def test_add_socket_if_came_up_and_process_unstarted(self):
        address = Address(ip="127.0.0.1", port=12345)
        
        self.fails = 0
        def callback(addr, errno):
            logger.debug("Adding address failed %s %d", addr, errno)
            self.fails += 1
            self._run_event.set()
        
        self.api1.socket_error_callback(callback)
        self.api1.add_socket(address.ip, address.port, address.family)
        self.api1.interface_came_up(address.ip, "lo", "lo", gateway="127.0.0.1")
        self.api1.start()
        
        self._run_event.wait(2) # Should be plenty of time
        self.assertEqual(self.fails, 0)
        
class TestAPINetworkInterface(unittest.TestCase):
    
    class MyWifiAPI(API):
        
        def __init__(self, name, *di_args, **di_kwargs):
            API.__init__(self, name, *di_args, **di_kwargs)
            self._run_event = Event()
            
        def run(self):
            ip = "193.156.108.78"
            port = 0
            self.add_socket(ip, port)
            event = Event()
            event.wait(2)
            if_ = "wlan0"
            os.system("ifconfig %s down" % if_)
            event.wait(20)
            while True:
                output = os.popen('ifconfig').read()
                index = output.find(if_)
                if index > 0:
                    wlan_config = output[index:]
                    m = re.search("inet addr:(\d+\.\d+\.\d+\.\d+)", wlan_config, re.IGNORECASE)
                    if m:
                        ip = m.groups()[0]
                    self.interface_came_up(ip, if_, if_[0:-1], None)
                    break
                event.wait(1)
            event.wait(1)
            self._run_event.set()
    
    def setUp(self):
        self.workdir = DISPERSY_WORKDIR + "/temp"
        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)
        self.api = self.MyWifiAPI("myapi", self.workdir, SWIFT_BINPATH, walker=True)


    def tearDown(self):
        if self.api:
            self.api.stop()
        
    def test_wifi_up_down(self):       
        self.restarted = False
        def restart_callback(error):
            self.restarted = True
            
        self.sock_errors = []
        def socket_callback(socket, error):
            self.sock_errors.append(error)
        
        self.api.swift_reset_callback(restart_callback)
        self.api.socket_error_callback(socket_callback)
        self.api.start()
        
        self.api._run_event.wait(40)
        
        self.assertFalse(self.restarted)
        self.assertEqual(self.sock_errors[0], 0) # Should be okay first
        self.assertEqual(self.sock_errors[-1], 0) # Last should be okay also
        


if __name__ == "__main__":
    unittest.main()