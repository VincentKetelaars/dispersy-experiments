from struct import pack, unpack_from

from ...conversion import BinaryConversion
from ...message import DropPacket


class DebugCommunityConversion(BinaryConversion):

    """
    DebugCommunityConversion is used to convert messages to and from binary while performing unittests.
    """
    def __init__(self, community, version="\x02"):
        assert isinstance(version, str), type(version)
        assert len(version) == 1, len(version)
        super(DebugCommunityConversion, self).__init__(community, version)
        # we use higher message identifiers to reduce the chance that we clash with either Dispersy (255 and down) and
        # normal communities (1 and up).
        self.define_meta_message(chr(101), community.get_meta_message(u"last-1-test"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(102), community.get_meta_message(u"last-9-test"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(103), community.get_meta_message(u"double-signed-text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(104), community.get_meta_message(u"full-sync-text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(105), community.get_meta_message(u"ASC-text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(106), community.get_meta_message(u"DESC-text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(107), community.get_meta_message(u"last-1-doublemember-text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(108), community.get_meta_message(u"protected-full-sync-text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(109), community.get_meta_message(u"dynamic-resolution-text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(110), community.get_meta_message(u"sequence-text"), self._encode_text, self._decode_text)
        self.define_meta_message(chr(111), community.get_meta_message(u"full-sync-global-time-pruning-text"), self._encode_text, self._decode_text)

    def _encode_text(self, message):
        """
        Encode a text message.
        Returns one byte containing len(message.payload.text) followed by this text.
        """
        return pack("!B", len(message.payload.text)), message.payload.text

    def _decode_text(self, placeholder, offset, data):
        """
        Decode a text message.
        Returns the new offset and a payload implementation.
        """
        if len(data) < offset + 1:
            raise DropPacket("Insufficient packet size")

        text_length, = unpack_from("!B", data, offset)
        offset += 1

        if len(data) < offset + text_length:
            raise DropPacket("Insufficient packet size")

        text = data[offset:offset + text_length]
        offset += text_length

        return offset, placeholder.meta.payload.implement(text)
