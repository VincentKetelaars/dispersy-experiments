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
    # For testing of tests
#     suite.addTest(unittest.TestLoader().loadTestsFromTestCase(test_endpoint.TestEndpointNoConnection))
    return suite

if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    test_suite = suite()
    runner.run(test_suite)