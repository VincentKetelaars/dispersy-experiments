'''
Created on Oct 11, 2013

@author: Vincent Ketelaars
'''
from threading import Event

from src.definitions import TIMEOUT_INTRODUCTION_REQUEST
from src.tools.runner import CallFunctionThread

from dispersy.logger import get_logger
logger = get_logger(__name__)

class IntroductionRequestTimeout(object):
    '''
    classdocs
    '''

    def __init__(self, helper_candidate, send_request):
        self.helper_candidate = helper_candidate
        self.send_request = send_request
        self.thread = CallFunctionThread()
        self.thread.put(self.wait_and_see)
        self.thread.start()
        
    def wait_and_see(self):
        Event().wait(TIMEOUT_INTRODUCTION_REQUEST)
        if not self.helper_candidate.introduction_response_received() or self.helper_candidate.send_bloomfilter_update:
            self.send_request()
            self.thread.put(self.wait_and_see)
        else:
            self.thread.stop()
            
    @property
    def candidate(self):
        return self.helper_candidate