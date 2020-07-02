import datetime as dt
import json
import base64
import threading
import asyncio
import queue

from typing import Optional, List, Dict, Union, Any, Tuple

import grpclib
from .grpc import model_pb2 as pb
from .grpc import model_grpc as pbx

from .types import \
    TopicDescription, \
    Subscription, \
    DataMessage
from .exceptions import Rejected

class ChatSession(object):
    """
    Represents a chat session that connects to a chat server and
    runs all internal `asyncio` coroutines on a `chat_event_loop`,
    which customarily runs on a background thread in an application.
    """
    def __init__(
        self,
        host,
        port,
        chat_event_loop,
        user_agent='python',
        ver='v0.16.5',
        device_id='1',
        lang='en-US',
        platform='web'):
        """
        Initialize a new chat session, connecting to a chat server
        running at `host`:`port`. All internal `asyncio`
        coroutines will run on the supplied `chat_event_loop`, which
        customarily runs on a background thread in an application.

        `user_agent`: String identifying client software. Expected to
        follow RFC 7231 section 5.5.3, but this is not enforced.

        `ver`: Version of the wire protocol supported by the client.

        `device_id`: Unique value which identifies this specific client
        device, such as for the purpose of push notifications. This is
        not interpreted by the server.

        `lang`: Human language of the client device.

        `platform`: Underlying OS of the client device for the purpose
        of push notifications; must be one of "android", "ios", "web". If
        missing, the server will try its best to detect the platform from
        the `user_agent` value.
        """

        # Parameters for connection and the internal chat event loop
        self.__host = host
        self.__port = port
        self.__chat_event_loop = chat_event_loop
        if self.__chat_event_loop is None:
            raise ValueError('No event loop supplied')

        # Parameters for identifying client to the server in hi message
        self.__user_agent=user_agent
        self.__ver = ver
        self.__device_id = device_id
        self.__lang = lang
        self.__platform = platform

        # Indicates that the message loop is running and the client is connected
        self.__ready_for_messages = threading.Event()

        # Internal chat event loop uses this to tell the client event loop about new responses
        self.__non_data_events = {}  # dict of dict of message ID to asyncio.Event

        # Client event loop waits on the appropriate asyncio.Event in __non_data_events and
        # then extracts the corresponding response from this
        self.__non_data_responses = {}  # dict of msg_type to (dict of message ID to msg)

        self.__data_event = asyncio.Event()
        self.__data_messages = queue.Queue()

        self.__user_id = None

        self.__stream: grpclib.client.Stream = None
        self.__message_loop_future = None
    
    async def messages(self):
        """
        Async generator of data messages sent from the server.
        """

        # Runs on the client event loop...
        # ... and that's why we don't just use a simple asyncio.Queue here,
        # as it would mean sharing an asyncio object across threads, which
        # they are not designed to do. asyncio is very NOT thread-safe

        while True:
            await self.__data_event.wait()  # TODO timeout
            self.__data_event.clear()
            # await-ing the asyncio.Event frees the internal chat event loop to
            # work on other tasks, making it a better choice than blocking until
            # the queue has an element (defeating the purpose of async IO!)
            while True:
                try:
                    msg = self.__data_messages.get_nowait()
                    yield msg
                except queue.Empty:
                    break
    
    @property
    def user_id(self) -> str:
        """
        ID of the currently authenticated user in this session.
        Raises `RuntimeError` if no user is authenticated.
        """

        if self.__user_id is None:
            raise RuntimeError('Not logged in yet')
        return self.__user_id

    _allowed_authentication_schemes_login = ['basic', 'token']
    _allowed_authentication_schemes_register = ['anonymous', 'basic']

    async def login(self, secret: str, scheme: str = 'basic') -> str:
        """
        Log in using the specified `secret`. `scheme` must be one of
        `basic` or `token`. This means that anonymous users, created
        using `register()` with `scheme="anynomous"`, are ephemeral
        and cannot log in again from a different session. `"basic"`
        requires a `secret` in the form `"<username>:<password>"`.

        Returns a `str` token that can be used for subsequent login
        attempts from different sessions using `scheme="token"`.
        """

        if scheme not in self._allowed_authentication_schemes_login:
            raise Rejected(f'Authentication scheme must be one of {self._allowed_authentication_schemes_login}')
        if isinstance(secret, str):
            secret = secret.encode('utf-8')
            if scheme == 'token':
                secret = base64.b64decode(secret)
        elif not isinstance(secret, bytes):
            raise Rejected(f'Authentication secret must be str or bytes')
        
        ctrl = await self.__send_message(pb.ClientMsg(
            login=pb.ClientLogin(
                scheme=scheme,
                secret=secret)))
        self.__user_id = json.loads(ctrl.params['user'].decode('utf-8'))
        token = ctrl.params['token']
        
        return json.loads(token.decode('utf-8')) if token is not None else None
    
    async def register(
        self,
        secret: Optional[str] = None,
        scheme: str = 'basic',
        login: bool = True,
        tags: Optional[List[str]] = None,
        public: Optional[bytes] = None,
        private: Optional[bytes] = None) -> str:

        """
        Create a new account with the specified `secret` and, if `login`
        is `True`, automatically log in using the new account.

        `scheme`: One of `"basic"` or `"anonymous"`. `"basic"` requires
        a `secret` in the form `"<username>:<password>"`. `secret` should
        be `None` for `"anonymous"`.

        `tags`: Arbitrary case-insensitive strings used for discovering
        users with `find_users()`. Tags may have a prefix which serves as
        a namespace, like `tel:14155551212`. Tags may not contain the
        double quote `"` but may contain spaces.

        `public`: Application-defined content to describe the user,
        visible to all users.

        `private`: Private application-defined content to describe the
        user, visible only to the user.

        Returns a `str` token that can be used for subsequent login
        attempts from different sessions using `scheme="token"`.
        """

        if scheme not in self._allowed_authentication_schemes_register:
            raise Rejected(f'Authentication scheme must be one of {self._allowed_authentication_schemes_register}')
        if isinstance(secret, str):
            secret = secret.encode('utf-8')
        elif not isinstance(secret, bytes) and scheme != 'anonymous':
            raise Rejected(f'Authentication secret must be str or bytes')

        ctrl = await self.__send_message(pb.ClientMsg(
            acc=pb.ClientAcc(
                user_id='new',
                scheme=scheme,
                secret=secret,
                login=login,
                tags=tags,
                desc=pb.SetDesc(
                    public=public,
                    private=private))))
        self.__user_id = json.loads(ctrl.params['user'].decode('utf-8'))
        token = ctrl.params['token']
        return json.loads(token.decode('utf-8')) if token is not None else None

    async def subscribe(self, topic: str):
        """
        Subscribe to the named `topic`.
        """

        await self.__send_message(pb.ClientMsg(
            sub=pb.ClientSub(
                topic=topic,  # topic to be subscribed or attached to
                # get_query=pb.GetQuery(...)
            )))
    
    async def new_topic(
        self,
        tags: Optional[List[str]] = None,
        public: Optional[bytes] = None,
        private: Optional[bytes] = None) -> str:

        """
        Create a new group topic and subscribe to it.

        `tags`: Arbitrary case-insensitive strings used for discovering
        topics with `find_topics()`. Tags may have a prefix which serves
        as a namespace, like `region:us`. Tags may not contain the double
        quote `"` but may contain spaces.

        `public`: Application-defined content to describe the topic,
        visible to all users using `get_topic_description()`.

        `private`: Per-user application-defined content to describe
        the topic, visible only to the current user.

        Returns the topic's name.
        """

        ctrl = await self.__send_message(pb.ClientMsg(
            sub=pb.ClientSub(
                topic="new",
                set_query=pb.SetQuery(
                    tags=tags,
                    desc=pb.SetDesc(
                        public=public,
                        private=private)))))
        return ctrl.topic
    
    async def leave(self, topic, unsubscribe=False):
        """
        Leave the named `topic`, which affects just the current session,
        and optionally `unsubscribe`, which will affect all sessions.
        """

        await self.__send_message(pb.ClientMsg(
            leave=pb.ClientLeave(
                topic=topic,
                unsub=unsubscribe)))
    
    async def publish_str(self, topic: str, content: str):
        """
        Like `publish()` but for a simple `str` message with no headers.

        Returns the `int` sequence ID of the delivered message.
        """
        
        return await self.publish(topic, json.dumps(content).encode('utf-8'))
    
    async def publish(self, topic: str, content: bytes,
        no_echo: bool = False,
        forwarded: Optional[str] = None,
        hashtags: Optional[List[str]] = None,
        mentions: Optional[List[str]] = None,
        mime: Optional[str] = None,
        priority: Optional[Any] = None,
        replace: Optional[str] = None,
        reply: Optional[str] = None,
        thread: Optional[str] = None,
        additional_headers: Optional[Dict[str, str]] = None):
        """
        Distribute content to subscribers to the named `topic`.
        Topic subscribers receive the supplied `content` and, unless
        `no_echo` is `True`, this originating session gets a copy
        of this message like any other currently attached session.

        Returns the `int` sequence ID of the delivered message.

        `forwarded`: Set to `"topic:seq_id"` to indicate that the
        message is a forwarded message.

        `hashtags`: A list of hashtags in this message, without
        the # symbol, e.g. `["onehash", "twohash"]`.

        `mentions`: A list of user IDs mentioned in this message
        (think @alice), e.g. `["usr1XUtEhjv6HND", "usr2il9suCbuko"]`.

        `mime`: MIME-type of this message content, e.g. `"text/x-drafty"`.
        The default value `None` is interpreted as `"text/plain"`.

        `priority`: Message display priority, or a hint for clients that
        this message should be displayed more prominently for a set period
        of time, e.g. `{"level": "high", "expires": "2019-10-06T18:07:30.038Z"}`.
        Think "starred" or "stickied" messages. Can only be set by the
        topic owner or an administrator (with 'A' permission). The `"expires"`
        field is optional.
        
        `replace`: Set to the `":seq_id"` of another message in this
        topic to indicate that this message is a correction or
        replacement for that message.

        `reply`: Set to the `":seq_id"` of another message in this topic
        to indicate that this message is a reply to that message.

        `thread`: To indicate that this message is part of a conversation
        thread in this topic, set to the `":seq_id"` of the first message
        in the thread. Intended for tagging a flat list of messages, not
        creating a tree.

        `additional_headers`: Additional application-specific headers
        which should begin with `"x-<application-name>-"`, although
        not yet enforced.
        """

        head = {}
        if forwarded is not None:
            head['forwarded'] = forwarded
        if hashtags is not None:
            head['hashtags'] = hashtags
        if mentions is not None:
            head['mentions'] = mentions
        if mime is not None:
            head['mime'] = mime
        if priority is not None:
            head['priority'] = priority
        if replace is not None:
            head['replace'] = replace
        if reply is not None:
            head['reply'] = reply
        if thread is not None:
            head['thread'] = thread
        if additional_headers is not None:
            for h in additional_headers:
                head[h] = additional_headers[h]

        await self.__send_message(pb.ClientMsg(
            pub=pb.ClientPub(
                topic=topic,
                no_echo=no_echo,
                head=head,
                content=content)))

    async def get_topic_description(self, topic: str, if_modified_since: Optional[Union[dt.datetime, int]] = None) -> TopicDescription:
        """
        Get a `TopicDescription` for the named `topic`.
        If `if_modified_since` is given, then public and private fields
        will be returned only if at least one of them has been updated
        after that timestamp.
        """

        if isinstance(if_modified_since, dt.datetime):
            # Convert dt.datetime to milliseconds since 1970 epoch
            if_modified_since = (if_modified_since - dt.datetime.utcfromtimestamp(0)).total_seconds() * 1000.0

        meta = await self.__send_message(pb.ClientMsg(
            get=pb.ClientGet(
                topic=topic,
                query=pb.GetQuery(
                    what='desc',  # query for topic description
                    desc=pb.GetOpts(
                        if_modified_since=if_modified_since)))))
        return TopicDescription(topic, meta.desc)
    
    async def get_subscribed_topics(
        self,
        limit: Optional[int] = None,
        if_modified_since: Optional[Union[dt.datetime, int]] = None) -> List[Subscription]:

        """
        Get a list of `Subscription` for every topic the current user is
        subscribed to.

        `limit`: Only return results for this many topics.

        `if_modified_since`: Only return public and private fields if at
        least one of them has been updated after this timestamp.
        """

        await self.subscribe('me')
        return await self.get_subscriptions('me', limit, if_modified_since)
    
    async def get_subscribed_users(
        self,
        topic: str,
        limit: Optional[int] = None,
        if_modified_since: Optional[Union[dt.datetime, int]] = None) -> List[Subscription]:

        """
        Get a list of `Subscription` for every user subscribed to the named
        `topic`.

        `limit`: Only return results for this many users.

        `if_modified_since`: Only return public and private fields if at
        least one of them has been updated after this timestamp.
        """

        return await self.get_subscriptions(topic, limit, if_modified_since)
    
    async def get_subscriptions(
        self,
        topic: str,
        limit: Optional[int] = None,
        if_modified_since: Optional[Union[dt.datetime, int]] = None) -> List[Subscription]:

        """
        Get a list of `Subscription` for every user subscribed to the named
        `topic`. If `topic == "me"` then get a list of `Subscription` for
        every topic the current user is subscribed to.
        
        `limit`: Only return this many subscribers.

        `if_modified_since`: Only return public and private fields if at
        least one of them has been updated after this timestamp.
        """

        if isinstance(if_modified_since, dt.datetime):
            # Convert dt.datetime to milliseconds since 1970 epoch
            if_modified_since = (if_modified_since - dt.datetime.utcfromtimestamp(0)).total_seconds() * 1000.0

        resp = await self.__send_message(pb.ClientMsg(
            get=pb.ClientGet(
                topic=topic,
                query=pb.GetQuery(
                    what='sub',  # query for subscribers
                    sub=pb.GetOpts(
                        if_modified_since=if_modified_since,
                        limit=limit)))))
        
        if isinstance(resp, pb.ServerMeta):
            return [Subscription(s) for s in resp.sub]
        return []  # pb.ServerCtrl means server OK'd the request and sent no results

    async def find_users(self, tag_query_string: str):
        await self.subscribe('fnd')
        await self.set_topic_description('fnd', public=json.dumps(tag_query_string).encode('utf-8'))
        topics_and_users = await self.get_subscriptions('fnd')
        users = [u for u in topics_and_users if u.user_id]
        return users

    async def find_topics(self, tag_query_string: str):
        await self.subscribe('fnd')
        await self.set_topic_description('fnd', public=json.dumps(tag_query_string).encode('utf-8'))
        topics_and_users = await self.get_subscriptions('fnd')
        topics = [t for t in topics_and_users if t.topic]
        return topics
    
    async def get_message_history(self, topic: str, since: Optional[int] = None, before: Optional[int] = None, limit: Optional[int] = None):
        """
        Get message history for the named `topic`. No return value;
        message history will come in through `messages()`, as usual.
        This method returns AFTER the message history comes in.

        `since`: Only return messages with sequence IDs greater than or
        equal to this integer (i.e., inclusive).

        `before`: Only return messages with sequence IDs less than this
        integer (i.e., exclusive).
        
        `limit`: Only return this many messages.
        """

        await self.__send_message(pb.ClientMsg(
            get=pb.ClientGet(
                topic=topic,
                query=pb.GetQuery(
                    what='data',
                    data=pb.GetOpts(
                        since_id=since,
                        before_id=before,
                        limit=limit)))))

    async def set_topic_description(
        self,
        topic: str,
        tags: Optional[List[str]] = None,
        public: Optional[bytes] = None,
        private: Optional[bytes] = None):
        
        """
        Update metadata of the named `topic`.

        `tags`: Arbitrary case-insensitive strings used for discovering
        topics with `find_topics()`. Tags may have a prefix which serves
        as a namespace, like `region:us`. Tags may not contain the double
        quote `"` but may contain spaces.

        `public`: Application-defined content to describe the topic,
        visible to all users using `get_topic_description()`. `None`
        will not clear the data; use a string with a single Unicode
        \u2421 character (\\u2421).

        `private`: Per-user application-defined content to describe
        the topic, visible only to the current user. `None` will not
        clear the data; use a string with a single Unicode \u2421
        character (\\u2421).
        """

        await self.__send_message(pb.ClientMsg(
            set=pb.ClientSet(
                topic=topic,
                query=pb.SetQuery(
                    tags=tags,
                    desc=pb.SetDesc(
                        public=public,
                        private=private)))))
        # TODO return a TopicDescription? is this ctrl or meta?

    async def delete_messages(self, topic: str, messages: Union[int, Tuple[int, int], List[Union[int, Tuple[int, int]]]], hard: bool = False):
        """
        Delete messages from the named `topic`.

        `messages`: A single message ID, a range of message IDs, or an
        array of message IDs and ranges of message IDs to delete. A
        range must be in the form of an inclusive-exclusive tuple. For
        example, `[65, (123, 126), (200, 201)]` will cause messages `65`,
        `123`, `124`, `125` and `200` to be deleted.

        If `hard` is `False`, then the messages will be hidden from
        the requesting user but still visible to other users. If
        `hard` is `True`, then the messages (`head` and `content`)
        will be deleted from storage, leaving a message stub, affecting
        all users.
        """

        if isinstance(messages, int):
            messages = [(messages, messages + 1)]
        elif isinstance(messages, tuple):
            messages = [messages]
        elif isinstance(messages, list):
            original_messages = messages
            messages = []
            for m in original_messages:
                if isinstance(m, int):
                    messages.append([(m, m + 1)])
                elif isinstance(m, tuple):
                    messages.append(m)
                else:
                    raise Rejected("Invalid format of 'messages' to delete")
        else:
            raise Rejected("Invalid format of 'messages' to delete")
        
        await self.__send_message(pb.ClientMsg(**{
            # 'del' is a reserved keyword in python, so we use dict expansion
            'del': pb.ClientDel(
                topic=topic,
                what=pb.ClientDel.MSG,
                del_seq=[pb.SeqRange(low=low, hi=hi) for low, hi in messages],
                hard=hard)
        }))
    
    async def delete_topic(self, topic: str):
        """
        Delete a topic, including all subscriptions and all messages. Only
        the owner can delete a topic. Peer-to-peer topics cannot be deleted.

        """
        await self.__send_message(pb.ClientMsg(**{
            # 'del' is a reserved keyword in python, so we use dict expansion
            'del': pb.ClientDel(
                topic=topic,
                what=pb.ClientDel.TOPIC,
                hard=True)
        }))

    async def notify_key_press(self, topic: str):
        """
        Forward an ephemeral notification to other clients currently
        attached to the named `topic` that the current user is
        composing a new message.

        This action is not acknowledged by the server and is silently
        dropped if invalid.
        """

        await self.__send_message(pb.ClientMsg(
            note=pb.ClientNote(
                topic=topic,
                what=pb.KP)),
            no_response=True)

    async def notify_received(self, topic: str, message: int):
        """
        Forward an ephemeral notification to other clients currently
        attached to the named `topic` that the current user has
        received the message with sequence ID `message`.

        Note that `get_topic_description()` returns the ID of the
        last received message in a topic.

        This action is not acknowledged by the server and is silently
        dropped if invalid.
        """

        await self.__send_message(pb.ClientMsg(
            note=pb.ClientNote(
                topic=topic,
                what=pb.RECV,
                seq_id=message)),
            no_response=True)

    async def notify_read(self, topic: str, message: int):
        """
        Forward an ephemeral notification to other clients currently
        attached to the named `topic` that the current user has
        read the message with sequence ID `message`.

        Note that `get_topic_description()` returns the ID of the
        last read message in a topic.

        This action is not acknowledged by the server and is silently
        dropped if invalid.
        """

        await self.__send_message(pb.ClientMsg(
            note=pb.ClientNote(
                topic=topic,
                what=pb.READ,
                seq_id=message)),
            no_response=True)
    
    async def close(self):
        """
        Close the current session and clean up any resources.
        Automatically called upon exit if using the
        `async with new_session():` async context manager pattern.
        """

        if self.__stream is not None:
            await self.__stream.cancel()
            self.__stream = None
        
        if self.__channel is not None:
            self.__channel.close()
            
        if self.__message_loop_future is not None:
            self.__message_loop_future.cancel()

    # region implementation details
    
    async def __aenter__(self):
        self.__ensure_message_loop_started()
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    __message_loop_lock = threading.Lock()
    
    def __ensure_message_loop_started(self):
        """
        Starts the "message loop", which allows messages to
        be sent to the chat server and which listens for
        messages received from the chat server.
        """

        with self.__message_loop_lock:
            if self.__message_loop_future is None:
                if not self.__chat_event_loop.is_running():
                    raise RuntimeError('Supplied event loop is not running')
                self.__message_loop_future = asyncio.run_coroutine_threadsafe(self.__message_loop(), self.__chat_event_loop)
        self.__ready_for_messages.wait()  # TODO timeout

    async def __message_loop(self):
        """
        On the internal chat event loop, open a gRPC channel
        to the chat server, make ourselves known to the server
        with a "hi" message, and start listening to messages
        from the server.
        """

        # Connect to the server
        self.__channel = grpclib.client.Channel(self.__host, self.__port)
        async with pbx.NodeStub(self.__channel).MessageLoop.open() as stream:
            # Say hello to the server
            await stream.send_message(pb.ClientMsg(
                hi=pb.ClientHi(
                    id='hello',
                    user_agent=self.__user_agent,
                    ver=self.__ver,
                    device_id=self.__device_id,
                    lang=self.__lang,
                    platform=self.__platform)))
            hi_resp = await stream.recv_message()  # TODO timeout
            
            # Tell producers that we are ready for business
            self.__stream = stream
            self.__ready_for_messages.set()

            # Handle responses from the server
            async for msg in stream:
                if msg.HasField('ctrl'):
                    await self.__handle_ctrl_msg(msg.ctrl)
                elif msg.HasField('meta'):
                    await self.__handle_meta_msg(msg.meta)
                elif msg.HasField('data'):
                    await self.__handle_data_msg(msg.data)
                # TODO handle 'pres', 'info', 'topic'

    async def __handle_ctrl_msg(self, ctrl):
        """ Runs on the internal chat event loop """

        self.__non_data_responses[ctrl.id] = ctrl
        ev = self.__non_data_events[ctrl.id]
        ev._loop.call_soon_threadsafe(ev.set)  # TODO this is private API but we need to set() it on the client event loop
    
    async def __handle_meta_msg(self, meta):
        """ Runs on the internal chat event loop """

        self.__non_data_responses[meta.id] = meta
        ev = self.__non_data_events[meta.id]
        ev._loop.call_soon_threadsafe(ev.set)  # TODO this is prviate API but we need to set() it on the client event loop

    async def __handle_data_msg(self, data):
        """ Runs on the internal chat event loop """

        # Available fields on 'data':
        # topic, from_user_id, timestamp, deleted_at, seq_id, head, content

        # Put the message on the queue
        self.__data_messages.put(DataMessage(data))

        # Set the asyncio.Event so the messages() async generator can yield messages
        ev = self.__data_event
        ev._loop.call_soon_threadsafe(ev.set)  # TODO this is private API but we need to set() it on the client event loop

    __next_message_id = 100
    __next_message_id_lock = threading.Lock()

    def __get_next_message_id(self) -> str:
        with self.__next_message_id_lock:
            self.__next_message_id += 1
            return str(self.__next_message_id)
    
    async def __send_message(self, message: pb.ClientMsg, no_response=False) -> Optional[Any]:
        """ Run on the client event loop """

        self.__ensure_message_loop_started()
        
        # Send the message to the server with a brand new message ID
        message_id = self.__get_next_message_id()
        self.__set_message_id(message, message_id)
        if not no_response:
            self.__non_data_events[message_id] = asyncio.Event()
        await self.__stream.send_message(message)
        
        # Wait for a response from the server
        if no_response:
            return
        
        await self.__non_data_events[message_id].wait()  # TODO timeout
        del self.__non_data_events[message_id]
        response = self.__non_data_responses.pop(message_id)
        
        # Handle the response's status code, if it's ctrl
        if isinstance(response, pb.ServerCtrl):
            self.__raise_for_ctrl_status(response)
        
        return response
    
    def __set_message_id(self, message: pb.ClientMsg, message_id: str):
        done = False
        for field in ['hi', 'acc', 'login', 'sub', 'leave', 'pub', 'get', 'set', 'del']:
            if message.HasField(field):
                if done:
                    raise RuntimeError('Too many message types in pb.ClientMsg instance')
                getattr(message, field).id = message_id
                done = True
        if not done and not message.HasField('note'):  # {note} is fire-and-forget
            raise RuntimeError('No message types in pb.ClientMsg instance')

    def __raise_for_ctrl_status(self, ctrl):
        if ctrl.code >= 400 and ctrl.code < 500:
            raise Rejected(ctrl.text)
        if ctrl.code >= 500 and ctrl.code < 600:
            raise RuntimeError(f'Server error: {ctrl.text}')

    # endregion


"""
TODO:
credentials
access
del what=sub
del what=topic
del what=user
del what=cred
"""