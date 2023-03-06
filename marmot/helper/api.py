"""Marmot API helpers
"""
from enum import Enum
from dataclasses import dataclass
from .crypto import (
    MarmotPublicKey,
    MarmotPrivateKey,
    hash_marmot_data,
    sign_marmot_data_digest,
    verify_marmot_data_digest,
)


class MarmotMessageLevel(Enum):
    """Marmot message level"""

    CRITICAL = 'CRITICAL'
    ERROR = 'ERROR'
    WARNING = 'WARNING'
    INFO = 'INFO'
    DEBUG = 'DEBUG'


MARMOT_MESSAGE_LEVELS = [lvl.value for lvl in MarmotMessageLevel]


@dataclass
class MarmotAPIMessage:
    """Marmot API message"""

    channel: str = ""
    content: str = ""
    whistler: str = ""
    signature: str = ""
    level: MarmotMessageLevel = MarmotMessageLevel.INFO

    @property
    def digest(self):
        """Message digest"""
        message_data = ':'.join([self.channel, self.level.value, self.content])
        return hash_marmot_data(message_data.encode())

    @classmethod
    def from_dict(cls, dct):
        """Create message object from dict"""
        return cls(
            channel=dct['channel'],
            content=dct['content'],
            whistler=dct['whistler'],
            level=MarmotMessageLevel(dct['level']),
            signature=dct['signature'],
        )

    def to_dict(self):
        """Convert message object to JSON serializable dict"""
        return {
            'channel': self.channel,
            'content': self.content,
            'whistler': self.whistler,
            'level': self.level.value,
            'signature': self.signature,
        }

    def sign(self, prikey: MarmotPrivateKey):
        """Update message signature"""
        self.signature = sign_marmot_data_digest(prikey, self.digest)
        return self

    def verify(self, pubkey: MarmotPublicKey):
        """Verify message signature"""
        return verify_marmot_data_digest(pubkey, self.digest, self.signature)
