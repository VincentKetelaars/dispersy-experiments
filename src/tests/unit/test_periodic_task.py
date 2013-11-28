'''
Created on Nov 27, 2013

@author: Vincent Ketelaars
'''
import unittest
from threading import Event

from src.tools.periodic_task import Looper, PeriodicTask

class TestPeriodicTask(unittest.TestCase):


    def test_max_iterations(self):
        sleep = 0.01
        looper = Looper(sleep)
        
        def test():
            pass
        
        max_it = 5
        looper.add_task(PeriodicTask(test, sleep, max_iterations=max_it))
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
        
        looper.add_task(PeriodicTask(test, sleep))
        looper.start()
        
        event = Event()
        event.wait(3 * sleep) # Take in account the unregularities
        
        self.assertGreater(self.counter, 0)
        
    def test_args(self):
        sleep = 0.01
        looper = Looper(sleep)
        
        self.counter = 0
        def test(multi=1):
            self.counter += 1 * multi 
        
        m = 10
        looper.add_task(PeriodicTask(test, sleep, kwargs={"multi":m}))
        looper.start()
        
        event = Event()
        event.wait(3 * sleep) # Take in account the unregularities
        
        self.assertEqual(self.counter % m, 0)

if __name__ == "__main__":
    unittest.main()