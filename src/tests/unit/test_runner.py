'''
Created on Oct 9, 2013

@author: Vincent Ketelaars
'''
import unittest
from threading import Event

from src.tests.unit.test_definitions import SMALL_TASK_TIMEOUT
from src.tools.runner import CallFunctionThread

from dispersy.logger import get_logger
logger = get_logger(__name__)

class RunnerTest(unittest.TestCase):

    def setUp(self):
        self._thread = CallFunctionThread()
        self._thread.start()

    def tearDown(self):
        self._thread.stop()

    def test_function(self):
        res = [1]
        res[0] = False;
        
        def callback():
            res[0] = True
            
        self._thread.put(callback)
        
        event = Event()
        event.wait(SMALL_TASK_TIMEOUT)
        
        self.assertTrue(res[0])
    
    def test_function_with_args(self):
        res = [1]
        res[0] = False;
        
        def callback(b, b2):
            res[0] = b and b2
            
        self._thread.put(callback,(True,),{"b2":True})
        
        event = Event()
        event.wait(SMALL_TASK_TIMEOUT)
        
        self.assertTrue(res[0])


if __name__ == "__main__":
    unittest.main()