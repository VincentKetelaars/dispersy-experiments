'''
Created on Nov 27, 2013

@author: Vincent Ketelaars
'''

from datetime import datetime, timedelta
from threading import Event, Thread

class PeriodicTask(object):
    '''
    Simple holder for a task that needs to be executed periodically.
    It contains the last time executed, function reference, arguments, time period and maximum iterations.
    '''

    def __init__(self, func, period, max_iterations=-1, args=(), kwargs={}):
        self.last_time = datetime.min
        self.iteration = 0
        self.max_iterations = max_iterations # -1 is infinite
        self.function = func
        self.period = timedelta(microseconds = period * 1000000) # period should be in seconds
        self.args = args # tuple
        self.kwargs = kwargs # dictionary
        
    def iterations_left(self):
        return self.max_iterations == -1 or self.max_iterations > self.iteration
        
    def have_to_go(self):
        return self.last_time + self.period < now()
    
    def call(self):
        self.last_time = now()
        self.iteration += 1
        self.function(*self.args, **self.kwargs)
        

class PeriodicIntroductionRequest(PeriodicTask):
    
    def __init__(self, func, period, candidate, args=(), kwargs={}):
        PeriodicTask.__init__(self, func, period, args=args, kwargs=kwargs)
        self.candidate = candidate

class Looper(Thread):
    """
    This Looper holds any number of periodic tasks and checks every timeout time if the task needs to be called
    or deleted
    """
    
    def __init__(self, sleep=0.1):
        Thread.__init__(self)
        self.setDaemon(True)
        self.sleep = sleep
        self.event = Event()
        self.tasks = []
        
    def run(self):
        while not self.event.is_set():
            marked_for_delete = []
            for task in self.tasks:
                if not task.iterations_left():
                    marked_for_delete.append(task)
                elif task.have_to_go():
                    task.call()
            
            for task in marked_for_delete:
                self.tasks.remove(task)
            del marked_for_delete
            self.event.wait(self.sleep)

    def add_task(self, periodic_task):
        assert isinstance(periodic_task, PeriodicTask)
        self.tasks.append(periodic_task)

    def stop(self):
        self.event.set()
 
def now():
    return datetime.utcnow()