'''
Created on Feb 19, 2014

@author: Vincent Ketelaars
'''
import unittest
from src.tools.priority_stack import PriorityStack


class TestPriorityStack(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass
    
    def test_stack_one_priority(self):
        stack = PriorityStack()
        self.assertEqual(stack.pop(), None)
        stack.put("z", ("blas"))
        stack.put("g", ("bla"))
        stack.put("a", ("blad"))
        stack.put("t", ("blaa"))
        self.assertEqual(stack.pop(), "blas")
        self.assertEqual(stack.pop(), "blaa")
        self.assertEqual(stack.pop(), "bla")
        self.assertEqual(stack.pop(), "blad")
        self.assertEqual(stack.pop(), None)

    def test_stack_two_priorities(self):
        stack = PriorityStack()
        self.assertEqual(stack.pop(), None)
        stack.put((2,2), ("blas"))
        stack.put((1,2), ("bla"))
        stack.put((1,1), ("blad"))
        stack.put((1,3), ("blaa"))
        self.assertEqual(stack.pop(), "blas")
        self.assertEqual(stack.pop(), "blaa")
        self.assertEqual(stack.pop(), "bla")
        self.assertEqual(stack.pop(), "blad")
        self.assertEqual(stack.pop(), None)
        
    def test_peek(self):
        stack = PriorityStack()
        self.assertEqual(stack.peek(), None)
        stack.put((2,2), ("blas"))
        stack.put((1,2), ("bla"))
        stack.put((1,1), ("blad"))
        stack.put((1,3), ("blaa"))
        self.assertEqual(stack.peek(), "blas")
        self.assertEqual(stack.pop(), "blas")
        self.assertEqual(stack.peek(), "blaa")
        self.assertEqual(stack.pop(), "blaa")
        self.assertEqual(stack.peek(), "bla")
        self.assertEqual(stack.pop(), "bla")
        self.assertEqual(stack.peek(), "blad")
        self.assertEqual(stack.pop(), "blad")
        self.assertEqual(stack.peek(), None)
        self.assertEqual(stack.pop(), None)
        
    def test_iter(self):
        stack = PriorityStack()
        stack.put((2,2), ("blas"))
        stack.put((1,2), ("bla"))
        stack.put((1,1), ("blad"))
        stack.put((1,3), ("blaa"))
        self.assertEqual(len(stack), 4)
        for i in stack:
            self.assertIsInstance(i, str)

if __name__ == "__main__":
    unittest.main()