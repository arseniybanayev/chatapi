import datetime as dt

from ..grpc import model_pb2 as pb

from typing import Optional, List, Dict, Union, Any, Tuple

class Subscription(object):
    """
    Smaller set of information about a topic's metadata than
    `TopicDescription`.
    """

    def __init__(self, sub: pb.TopicSub):
        self.__sub = sub
    
    @property
    def user_id(self) -> str:
        return self.__sub.user_id

    @property
    def topic(self) -> str:
        return self.__sub.topic
    
    @property
    def last_message_timestamp(self) -> Optional[dt.datetime]:
        """
        Timestamp of the last message
        """

        if self.__sub.touched_at is not None:
            # utcfromtimestamp takes seconds, not milliseconds
            return dt.datetime.utcfromtimestamp(self.__sub.touched_at / 1000.0)
        return None

    @property
    def last_message_id(self) -> str:
        """ ID of the last message """
        return self.__sub.seq_id

    @property
    def p2p_last_seen_at(self) -> Optional[dt.datetime]:
        """
        Timestamp when the peer was last online.
        Only available for peer-to-peer topics; `None` for group topics.
        """
        if self.__sub.last_seen_time is not None:
            # utcfromtimestamp takes seconds, not milliseconds
            return dt.datetime.utcfromtimestamp(self.__sub.last_seen_time / 1000.0)
        return None
    
    @property
    def p2p_last_seen_user_agent(self) -> Optional[str]:
        """
        User agent of the peer when the peer was last online.
        Only available for peer-to-peer topics; `None` for group topics.
        """
        return self.__sub.last_seen_user_agent
    
    @property
    def public(self) -> Optional[bytes]:
        """
        The `public` field of the topic or user. For peer-to-peer topics,
        this is the `public` field of the peer.
        """
        
        return self.__sub.public
    
    @property
    def private(self) -> Optional[bytes]:
        """
        The `private` field of the topic or user, available only to the
        current user.
        """
        return self.__sub.private
