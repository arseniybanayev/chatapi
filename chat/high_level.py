import datetime as dt

from . import session

class Topic(object):
    """
    A named communication channel between two or more people.
    """

    def __init__(self, session: session.ChatSession, name: str):
        self.__session = session
        self.__name = name

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

    async def get_description(self) :
        """
        Gets information about the topic's metadata from the server.
        """

        return await self.__session.get_topic_description(self.__name)
        # self.__last_get_description_timestamp = dt.datetime.utcnow()
    
    async def send_message(self):
        pass
    
    