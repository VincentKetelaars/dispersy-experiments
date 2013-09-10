'''
Created on Sep 10, 2013

@author: Vincent Ketelaars
'''
import unittest

from src.filepusher import FilePusher

class Test(unittest.TestCase):


    def setUp(self):
        pass


    def tearDown(self):
        pass


    def test_directory_with_slash(self):
        directory = "/"
        filepusher = FilePusher


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.test_directory_with_slash']
    unittest.main()