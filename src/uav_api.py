'''
Created on Nov 28, 2013

@author: Vincent Ketelaars
'''
from threading import Event

from Common.Status.StatusDbReader import StatusDbReader

from src.logger import get_logger
from src.api import API

logger = get_logger(__name__)

class UAVAPI(API):
    '''
    This class will be the bridge between Dispersy / Libswift and the current UAV system.
    Particularly it will monitor the status of the channels on the UAV, using StatusDbReader.
    At the moment this is still pull based, but this could change.
    '''


    def __init__(self, *di_args, **di_kwargs):
        '''
        @param di_args: Tuple of arguments for DispersyInstance
        @param di_kwargs: Dictionary of arguments for DispersyInstance
        '''
        API.__init__(self, *di_args, **di_kwargs)
        self.db_reader = StatusDbReader()
        self.run_event = Event()
        self.sleep = 5
        
    def run(self):
        while not self.run_event.is_set():
            try:
                channels = self.db_reader.get_channels()
                logger.debug("I have got channels you'll\n%s", channels)
            except:
                logger.exception("To bad")
            self.run_event.wait(self.sleep)
    
    def stop(self):
        self.run_event.set()
        API.stop()
        
if __name__ == "__main__":
    from src.main import main
    main(UAVAPI)