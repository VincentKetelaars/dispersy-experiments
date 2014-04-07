# This file is just for compatibility with python 2.5, which has
# the "is_set()" of the threading.Event class called "isSet()"....

from threading import RLock,Lock,Thread,_Event,Timer,currentThread,Condition

try:
    e = _Event()
    e.__getattribute__("is_set_")
    from threading import Event
    
except AttributeError, e:
    #print " ** Compatibility mode **"

    class Event(_Event):

        def __init__(self):
            _Event.__init__(self)
        def is_set(self):
            return self.isSet()
    
