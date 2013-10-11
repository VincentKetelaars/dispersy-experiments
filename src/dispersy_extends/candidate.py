'''
Created on Oct 11, 2013

@author: Vincent Ketelaars
'''

from dispersy.candidate import WalkCandidate, CANDIDATE_WALK_LIFETIME, CANDIDATE_STUMBLE_LIFETIME, CANDIDATE_INTRO_LIFETIME

class EligbleWalkCandidate(WalkCandidate):
    '''
    classdocs
    '''

    def is_eligible_for_walk(self, now):
        return (self._last_walk + self._timeout_adjustment <= now < self._last_walk + CANDIDATE_WALK_LIFETIME or 
                now < self._last_stumble + CANDIDATE_STUMBLE_LIFETIME or now < self._last_intro + CANDIDATE_INTRO_LIFETIME)