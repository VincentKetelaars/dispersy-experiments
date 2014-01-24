'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''
import sys
from os.path import exists
from logging.config import fileConfig
from logging import basicConfig, DEBUG
from ConfigParser import NoSectionError

logfile = "logger.conf"

if exists(logfile):
    try:
        fileConfig(logfile)
        print logfile, "configured logging"
    except (IOError, NoSectionError):
        basicConfig(stream = sys.stderr, level=DEBUG, format='%(filename)s:%(lineno)s %(levelname)s:%(message)s')
        print "Could not open", logfile, sys.exc_info()
else:
    print logfile, "does not exist"