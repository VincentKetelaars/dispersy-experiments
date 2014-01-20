'''
Created on Nov 28, 2013

@author: Vincent Ketelaars
'''
import sys

import dispersy.logger as dlogger
import inspect


def get_logger(name):
    logger = dlogger.get_logger(name)
    return logger

def get_uav_logger(name):
    uav_logger = None
    try:
        from Common.API import get_log
        uav_logger = get_log(name)
    except ImportError:
        pass    
#     logger.addHandler(logging.StreamHandler(sys.stderr))
#     logger.setLevel(logging.DEBUG)
    return UAVLoggerWrapper(uav_logger, name)

class UAVLoggerWrapper(object):
    
    def __init__(self, logger, name):
        self.logger = logger
        self.name = name
        # TODO: Get lineno as well
        # Dict can be added as extra=self.dict
        
    def debug(self, *args):
        if self.logger is not None:
            self.logger.debug(*args, extra=self.get_dict())
            
    def info(self, *args):
        if self.logger is not None:
            self.logger.info(*args, extra=self.get_dict())
        
    def warning(self, *args):
        if self.logger is not None:
            self.logger.warning(*args, extra=self.get_dict())
        
    def error(self, *args):
        if self.logger is not None:
            self.logger.error(*args, extra=self.get_dict())
            
    def get_dict(self):
        d = {}
#         lineno = self._get("lineno")
#         if lineno is not None:
#             d["lineno"] = lineno # Get caller line number
#             d["module"] = self.name # Caller name
        return d
            
    def _get(self, arg):
        return self._get_caller().get(arg)
            
    def _get_caller(self):
        frame, filename, lineno, func, lines, index = inspect.getouterframes(inspect.currentframe())[1]
        return {"frame" : frame, "filename" : filename, "lineno" : lineno, "function_name" : func, 
                "lines" : lines, "index" : index}