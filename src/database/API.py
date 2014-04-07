"""

Common API for all UAV based code


"""
import socket
import os
import time


import src.database.CompatThreading as threading
from src.database import Status
from src.database.Config import Configuration
from src.logger import get_logger

logger = get_logger(__name__)
    
class MissingConfigException(Exception):
    pass

# Global stop-event for everything instantiated by the API
global api_stop_event
api_stop_event = threading.Event()

import logging
log_level_str = {"CRITICAL": logging.CRITICAL,
                 "FATAL"   : logging.FATAL,
                 "ERROR"   : logging.ERROR,
                 "WARNING" : logging.WARNING,
                 "INFO"    : logging.INFO,
                 "DEBUG"   : logging.DEBUG}

log_level = {logging.CRITICAL: "CRITICAL",
             logging.FATAL   : "FATAL",
             logging.ERROR   : "ERROR",
             logging.WARNING : "WARNING",
             logging.INFO    : "INFO",
             logging.DEBUG   : "DEBUG"}

# Configuration file
#This is the path of the configuration file
#configService_file = "./Config/configuration.xml"

global CONFIGS
CONFIGS = {} 

global glblStatusReporter
glblStatusReporter = None

def get_status_reporter():
    global glblStatusReporter
    if not glblStatusReporter:
        from Common.Status.MySQLReporter import MySQLStatusReporter as DBReporter
        glblStatusReporter = DBReporter()
    return glblStatusReporter
        
class ReporterCollection:
    """
    This is just a class to hold remote status holders that stops and cleans
    up all reporters
    """
    singleton = "None"

    def __init__(self):
        global api_stop_event
        self.stop_event = api_stop_event
        self.lock = threading.Lock()
        
        self.reporters = {}
        
        try:
            from Common.Status.MySQLReporter import MySQLStatusReporter as DBReporter
            name = "System.Status.MySQL"
        except Exception, e:
            print "Exception importing MySQL destination:", e
            from Common.Status.Sqlite3Reporter import DBStatusReporter as DBReporter
            name = "System.Status.Sqlite"

        self.db_reporter = DBReporter(name)

    @staticmethod
    def get_singleton():
        if ReporterCollection.singleton == "None":
            print "CREATING NEW ReporterCollection"
            ReporterCollection.singleton = ReporterCollection()
        return ReporterCollection.singleton

    def get_db_reporter(self):
        return self.db_reporter
    
    def get_reporter(self, name):
        """
        @returns (was_created, reporter) where was_created is True iff the
        reporter was just created
        """
        was_created = False
        self.lock.acquire()
        try:
            if not name in self.reporters:
                was_created = True
                from Common.Status.RemoteStatusReporter import RemoteStatusReporter
                self.reporters[name] = RemoteStatusReporter(name, self.stop_event)
                # Register this reporter with the UAV service
                import Common.timeout_xmlrpclib as xmlrpclib
                try:
                    cfg = get_config("System.Status.RemoteStatusReporter")
                    service = xmlrpclib.ServerProxy(cfg["url"], timeout=1.0)
                    error = None
                    for i in range(0, 3):
                        try:
                            service.add_holder(name, socket.gethostname(),
                                               self.reporters[name].get_port())
                            error = None
                            break
                        except socket.error, e:
                            print "Error registering status reporter:", e
                            error = e
                            os.system("python Services/StatusService.py & ")
                            print "*** Started status service"
                            time.sleep(2)
                    if error:
                        raise error
                except:
                    logger.exception("Could not register remote status reporter '%s' with service on port '%s'"%(name, self.reporters[name].get_port()))
                
            return (was_created, self.reporters[name])
        finally:
            self.lock.release()

    def __del__(self):
        self.stop_event.set()
        
reporter_collection = None

def shutdown():
    """
    Shut the API down properly
    """

    global api_stop_event
    api_stop_event.set()

    global reporter_collection
    del reporter_collection
    reporter_collection = None


def reset():
    """
    Reset API state.  This function is not completed, but has been 
    made to handle multiprocess "forks" that make copies of state
    it really should not copy.
    
    Perhaps a better way is to ensure that all external connections are 
    dependent on thread-id + process id?
    """
    #from Common.loggingService import resetLoggingService

    #resetLoggingService()
    shutdown()
    
    global api_stop_event
    api_stop_event = threading.Event()

#@logTiming
def get_config(name = None, version="default"):
    """
    Rewritten to return configWrappers, that wrap a 
    configManagerClient singleton due to heavy resource usage
    """
    global CONFIGS
    if not (name, version) in CONFIGS:
        CONFIGS[(name, version)] = Configuration(root=name, 
                                                 stop_event=api_stop_event,
                                                 version=version)
    return CONFIGS[(name, version)]

#@logTiming
def get_status(name):
    holder = Status.get_status_holder(name, api_stop_event)
    try:
        holder.add_reporter(get_status_reporter())
    except Exception,e:
        print "Database reporter could not be added:",e
    return holder

    (was_created, reporter) = ReporterCollection.get_singleton().get_reporter(name)
    if was_created:
        try:
            holder.add_reporter(reporter)
            holder["remote_port"] = reporter.port
            #print "REPORTER available on port", reporter.port
        except Exception, e:
            print "Remote reporter could not be added:",e
            
        try:
            holder.add_reporter(ReporterCollection.get_singleton().get_db_reporter())
        except Exception,e:
            print "Database reporter could not be added:",e

    return holder
