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

class TopicDescription(object):
    """ Information about a topic's metadata. """

    def __init__(self, name, desc: pb.TopicDesc):
        self.__name = name
        self.__desc = desc
        
    @property
    def name(self) -> str:
        """
        The name of the topic, from the perspective of the current
        session. In a peer-to-peer topic, each participant sees the
        topic name as the user ID of the other participant. In any
        other topic, every participant sees the same topic name. The
        name is assigned by the server.
        """

        return self.__name

    @property
    def created_at(self) -> Optional[dt.datetime]:
        """ Timestamp of topic creation """
        if self.__desc.created_at is not None:
            # utcfromtimestamp takes seconds, not milliseconds
            return dt.datetime.utcfromtimestamp(self.__desc.created_at / 1000.0)
        return None
    
    @property
    def updated_at(self) -> Optional[dt.datetime]:
        """ Timestamp of last topic update """
        if self.__desc.updated_at is not None:
            # utcfromtimestamp takes seconds, not milliseconds
            return dt.datetime.utcfromtimestamp(self.__desc.updated_at / 1000.0)
        return None
    
    @property
    def default_authenticated_access(self) -> str:
        """ Topic's default access permissions for authenticated users """
        return self.__desc.defacs.auth
    
    @property
    def default_anonymous_access(self) -> str:
        """ Topic's default access permissions for anonymous users """
        return self.__desc.defacs.anon

    @property
    def requested_user_access(self) -> str:
        """ User's requetsed access permissions for this topic """
        return self.__desc.acs.want
    
    @property
    def actual_user_access(self) -> str:
        """ User's granted access permissions for this topic """
        return self.__desc.acs.given
    
    @property
    def last_message_id(self) -> int:
        """ ID of the last message """
        return self.__desc.seq_id
    
    @property
    def read_message_id(self) -> int:
        """ ID of the last message the user claims to have read """
        return self.__desc.read_id
    
    @property
    def received_message_id(self) -> int:
        """ ID of the last message the user claims to have received """
        return self.__desc.recv_id
    
    @property
    def last_deleted_message_id(self) -> int:
        """ ID of the last deleted message, if any """
        return self.__desc.del_id

    @property
    def public(self) -> bytes:
        """
        Application-defined data available to all topic subscribers.
        For peer-to-peer topics, this is the `public` field of the
        other user.
        """
        
        return self.__desc.public
    
    @property
    def private(self) -> bytes:
        """ Application-defined data available only to the curent user """
        return self.__desc.private
