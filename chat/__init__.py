from typing import Union

from .loop import ChatLoop
from .session import ChatSession
from .types import DataMessage, Subscription, TopicDescription
from .exceptions import Rejected


def quick_connect(host: str, port: Union[str, int]) -> ChatSession:
    loop = ChatLoop(host, port)
    session = loop.new_session()
    return session


def new_loop(host: str, port: Union[str, int]) -> ChatLoop:
    loop = ChatLoop(host, port)
    return loop