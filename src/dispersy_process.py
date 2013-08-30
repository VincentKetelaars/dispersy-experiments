'''
Created on Aug 29, 2013

@author: Vincent Ketelaars
'''

class DispersyProcess(object):
    '''
    classdocs
    '''


    def __init__(self, process, pipe):
        '''
        Constructor
        '''
        self.__process = process
        self.__pipe = pipe
        self.__lan = None

    def get_process(self):
        return self.__process

    def get_pipe(self):
        return self.__pipe
    
    def get_lan(self):
        return self.__lan
    

    def set_process(self, process):
        self.__process = process

    def set_pipe(self, pipe):
        self.__pipe = pipe
        
    def set_lan(self, lan):
        self.__lan = lan
        
    
    lan = property(get_lan, set_lan)
    process = property(get_process, set_process)
    pipe = property(get_pipe, set_pipe)
    
        