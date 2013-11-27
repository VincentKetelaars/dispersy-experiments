'''
Created on Nov 27, 2013

@author: Vincent Ketelaars
'''
import unittest
from threading import Event

from src.tools.periodic_task import Looper

class TestPeriodicTask(unittest.TestCase):


    def test_max_iterations(self):
        sleep = 0.01
        looper = Looper(sleep)
        
        def test():
            print "test"
        
        max_it = 5
        looper.add_task(test, sleep, max_iterations=max_it)
        looper.start()
        
        event = Event()
        event.wait((max_it + 1) * sleep) # Take in account the unregularities
        
        self.assertEqual(len(looper.tasks), 0)
        
    def test_call(self):
        sleep = 0.01
        looper = Looper(sleep)
        
        self.counter = 0
        def test():
            self.counter += 1
        
        looper.add_task(test, sleep)
        looper.start()
        
        event = Event()
        event.wait(3 * sleep) # Take in account the unregularities
        
        self.assertGreater(self.counter, 0)

if __name__ == "__main__":
    unittest.main()