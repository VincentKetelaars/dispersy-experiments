'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''
from os.path import exists
from logging.config import fileConfig
    
if exists("logger.conf"):
    fileConfig("logger.conf")