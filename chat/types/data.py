import datetime as dt
import json

from ..grpc import model_pb2 as pb

from typing import Optional, List, Dict, Union, Any, Tuple

class DataMessage(object):
    """
    Represents a published data message in a topic.
    """

    def __init__(self, data: pb.ServerData):
        self.__data = data
    
    @property
    def from_user_id(self) -> str:
        """ ID of the user who originated the data message """
        return self.__data.from_user_id
    
    @property
    def timestamp(self) -> dt.datetime:
        """ Timestamp when the data message was sent """
        # utcfromtimestamp takes seconds, not milliseconds
        return dt.datetime.utcfromtimestamp(self.__data.timestamp / 1000.0)
    
    @property
    def timestamp_deleted(self) -> Optional[dt.datetime]:
        """ Timestamp when the data message was deleted, otherwise `None` """
        if self.__data.deleted_at is not None and self.__data.deleted_at != 0:
            # utcfromtimestamp takes seconds, not milliseconds
            return dt.datetime.utcfromtimestamp(self.__data.deleted_at / 1000.0)
        return None
    
    @property
    def id(self) -> int:
        """ ID of the data message """
        return self.__data.seq_id

    @property
    def content(self) -> bytes:
        return self.__data.content
    
    @property
    def content_str(self) -> str:
        return json.loads(self.content.decode('utf-8'))

    @property
    def headers(self) -> Dict[str, bytes]:
        return self.__data.head
        # """
        # Distribute content to subscribers to the named `topic`.
        # Topic subscribers receive the supplied `content` and, unless
        # `no_echo` is `True`, this originating session gets a copy
        # of this message like any other currently attached session.

        # `forwarded`: Set to `"topic:seq_id"` to indicate that the
        # message is a forwarded message.

        # `hashtags`: A list of hashtags in this message, without
        # the # symbol, e.g. `["onehash", "twohash"]`.

        # `mentions`: A list of user IDs mentioned in this message
        # (think @alice), e.g. `["usr1XUtEhjv6HND", "usr2il9suCbuko"]`.

        # `mime`: MIME-type of this message content, e.g. `"text/x-drafty"`.
        # The default value `None` is interpreted as `"text/plain"`.

        # `priority`: Message display priority, or a hint for clients that
        # this message should be displayed more prominently for a set period
        # of time, e.g. `{"level": "high", "expires": "2019-10-06T18:07:30.038Z"}`.
        # Think "starred" or "stickied" messages. Can only be set by the
        # topic owner or an administrator (with 'A' permission). The `"expires"`
        # field is optional.
        
        # `replace`: Set to the `":seq_id"` of another message in this
        # topic to indicate that this message is a correction or
        # replacement for that message.

        # `reply`: Set to the `":seq_id"` of another message in this topic
        # to indicate that this message is a reply to that message.

        # `thread`: To indicate that this message is part of a conversation
        # thread in this topic, set to the `":seq_id"` of the first message
        # in the thread. Intended for tagging a flat list of messages, not
        # creating a tree.

        # `additional_headers`: Additional application-specific headers
        # which should begin with `"x-<application-name>-"`, although
        # not yet enforced.
        # """
