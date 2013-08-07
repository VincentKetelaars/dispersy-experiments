'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''

from dispersy.community import Community
from dispersy.conversion import DefaultConversion

from conversion import MyConversion

class MyCommunity(Community):
    '''
    classdocs
    '''


    def __init__(self, dispersy, master_member):
        '''
        Constructor
        '''
        print "Yeah!", dispersy, master_member
        super(MyCommunity, self).__init__(dispersy, master_member)
        
    def initiate_conversions(self):
        """
        Overwrite
        """
        return [DefaultConversion(self), MyConversion(self)]
    
    def initiate_meta_messages(self):
        """
        Overwrite
        """
        return [Message()]