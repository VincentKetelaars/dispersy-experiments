'''
Created on Sep 17, 2013

@author: Vincent Ketelaars
'''
import unittest
from test_filepusher import TestFilePusher
import test_community
import test_conversion
import test_endpoint
import test_runner
import test_address
import test_download
import test_api
import test_dispersy_instance
import test_periodic_task
import test_swift_community
import test_dispersy_contact
import test_peer
import test_priority_stack

def suite():
    suite = unittest.TestSuite()
    suite.addTest(TestFilePusher('test_dir_and_files')) # If this one succeeds, test_directory does not have to run
    suite.addTest(TestFilePusher('test_files'))
    suite.addTest(TestFilePusher('test_directory'))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_community))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_conversion))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_endpoint))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_runner))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_address))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_download))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_api))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_dispersy_instance))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_periodic_task))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_swift_community))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_dispersy_contact))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_peer))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_priority_stack))
    # For testing of tests
#     suite.addTest(unittest.TestLoader().loadTestsFromTestCase(test_endpoint.TestEndpointNoConnection))
    return suite

if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    test_suite = suite()
    runner.run(test_suite)