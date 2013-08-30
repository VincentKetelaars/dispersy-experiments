import logging
logger = logging.getLogger(__name__)

from time import time

from .dispersytestclass import DispersyTestFunc, call_on_dispersy_thread
from .debugcommunity.community import DebugCommunity

class TestNATDetection(DispersyTestFunc):
    """
    Tests NAT detection.

    These unit tests should cover all methods which are related to detecting the NAT type of a peer.
    """

    def _emulate_connection_type__unknown(self, community):
        logger.debug("Emulating connection type: UNKNOWN")
        address = ("127.0.0.2", 1)
        candidate = community.create_candidate(address, False, address, address, u"unknown")
        self._dispersy.wan_address_vote(("127.0.0.1", 1), candidate)

        # because we CANDIDATE didn't send any messages to COMMUNITY, the CANDIDATE timestamps have never been set.  In
        # the current code this results in the CANDIDATE to remain 'obsolete'.
        self.assertTrue(candidate.is_obsolete(time()))

        self.assertNotEqual(self._dispersy.lan_address, self._dispersy.wan_address)
        self.assertEqual(self._dispersy.connection_type, u"unknown")

    def _emulate_connection_type__public(self, community):
        logger.debug("Emulating connection type: PUBLIC")
        for i in range(5):
            address = ("127.0.0.3", i + 1)
            candidate = community.create_candidate(address, False, address, address, u"unknown")
            self._dispersy.wan_address_vote(self._dispersy.lan_address, candidate)

            # because we CANDIDATE didn't send any messages to COMMUNITY, the CANDIDATE timestamps have never been set.  In
            # the current code this results in the CANDIDATE to remain 'obsolete'.
            self.assertTrue(candidate.is_obsolete(time()))

            # one vote is enough, but more won't hurt
            self.assertEqual(self._dispersy.lan_address, self._dispersy.wan_address)
            self.assertEqual(self._dispersy.connection_type, u"public")

    def _emulate_connection_type__symmetric_nat(self, community):
        logger.debug("Emulating connection type: SYMMETRIC-NAT")
        for i in range(5):
            address = ("127.0.0.4", i + 1)
            candidate = community.create_candidate(address, False, address, address, u"unknown")
            self._dispersy.wan_address_vote(("127.0.0.1", i + 1), candidate)

            # because we CANDIDATE didn't send any messages to COMMUNITY, the CANDIDATE timestamps have never been set.  In
            # the current code this results in the CANDIDATE to remain 'obsolete'.
            self.assertTrue(candidate.is_obsolete(time()))

            if i > 0:
                # two votes are needed, but more won't hurt
                self.assertNotEqual(self._dispersy.lan_address, self._dispersy.wan_address)
                self.assertEqual(self._dispersy.connection_type, u"symmetric-NAT")

    def _clear_votes(self, community):
        logger.debug("Cleanup votes")
        self.assertGreater(community.cleanup_candidates(), 0)
        self.assertEqual(len(self._dispersy._wan_address_votes), 0)

    @call_on_dispersy_thread
    def test_connection_type(self, *types):
        """
        Tests the transition between connection types based on external votes.
        """
        community = DebugCommunity.create_community(self._dispersy, self._my_member)

        self._emulate_connection_type__public(community)
        self._clear_votes(community)
        self._emulate_connection_type__unknown(community)
        self._clear_votes(community)
        self._emulate_connection_type__public(community)
        self._clear_votes(community)
        self._emulate_connection_type__symmetric_nat(community)
        self._clear_votes(community)
        self._emulate_connection_type__unknown(community)
        self._clear_votes(community)
        self._emulate_connection_type__symmetric_nat(community)
        self._clear_votes(community)
        self._emulate_connection_type__public(community)

    @call_on_dispersy_thread
    def test_symmetric_vote(self):
        """
        Tests symmetric-NAT detection.

        1. After receiving two votes from different candidates A and B for different port numbers, a peer must change
           it's connection type to summetric-NAT.

        2. After candidate A and B are gone and a only votes for the same port number remains, a peer must change it's
           connection type back to unknown or public.
        """
        community = DebugCommunity.create_community(self._dispersy, self._my_member)

        for i in range(2):
            address = ("127.0.0.2", i + 1)
            candidate = community.create_candidate(address, False, address, address, u"unknown")
            self._dispersy.wan_address_vote(("127.0.0.1", i + 1), candidate)
        self.assertEqual(self._dispersy.connection_type, u"symmetric-NAT")

        # because we CANDIDATE didn't send any messages to COMMUNITY, the CANDIDATE timestamps have never been set.  In
        # the current code this results in the CANDIDATE to remain 'obsolete'.
        self.assertTrue(candidate.is_obsolete(time()))
        self.assertEqual(community.cleanup_candidates(), 2)

        for i in range(2):
            address = ("127.0.0.3", i + 1)
            candidate = community.create_candidate(address, False, address, address, u"unknown")
            self._dispersy.wan_address_vote(("127.0.0.1", 1), candidate)
        self.assertEqual(self._dispersy.connection_type, u"unknown")
