'''
Created on Sep 17, 2013

@author: Vincent Ketelaars
'''
import unittest
from test_filepusher import TestFilePusher
import test_community
import test_conversion
import test_endpoint

def suite():
    suite = unittest.TestSuite()
    suite.addTest(TestFilePusher('test_dir_and_files'))
    suite.addTest(TestFilePusher('test_files'))
    suite.addTest(TestFilePusher('test_directory'))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_community))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_conversion))
    suite.addTest(unittest.TestLoader().loadTestsFromModule(test_endpoint))
    return suite

if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    test_suite = suite()
    runner.run(test_suite)