import datetime as dt
import pytest
import asyncio
import os
import json

from concurrent import futures

from ..chat.loop import ChatLoop
from ..chat.session import ChatSession, Rejected

os.environ['CHAT_HOST'] = 'tinode-server'
os.environ['CHAT_PORT'] = '16060'

def same_elements_in_lists(list1, list2):
    list1 = list(list1)
    try:
        for r in list2:
            list1.remove(r)
    except ValueError:
        return False
    return not list1

@pytest.fixture(scope='module')
def loop():
    loop = ChatLoop(os.environ['CHAT_HOST'], os.environ['CHAT_PORT'])
    yield loop
    loop.stop()

def random_secret():
    return f'{os.urandom(8).hex()}:{os.urandom(8).hex()}'

@pytest.mark.asyncio
async def test_message_loop(loop: ChatLoop):
    async with loop.new_session() as s:
        s._ChatSession__ensure_message_loop_started()
        assert isinstance(s._ChatSession__message_loop_future, futures.Future) 
        assert not s._ChatSession__message_loop_future.done()
        assert s._ChatSession__stream is not None
    assert s._ChatSession__message_loop_future.done()

@pytest.mark.asyncio
async def test_user_id_property(loop: ChatLoop):
    async with loop.new_session() as s:
        with pytest.raises(RuntimeError):
            user_id = s.user_id
        secret = random_secret()
        with pytest.raises(Rejected):
            await s.login(secret)
        with pytest.raises(RuntimeError):
            user_id = s.user_id
        await s.register(secret)
        assert s.user_id is not None

@pytest.mark.asyncio
async def test_register_basic(loop):
    # Register a new user with basic auth
    async with loop.new_session() as s:
        token = await s.register(random_secret())
        assert token is not None
        user_id = s.user_id
        assert user_id is not None
    
    # Log in again using this token
    async with loop.new_session() as s:
        assert token == await s.login(scheme='token', secret=token)
        assert user_id == s.user_id

@pytest.mark.asyncio
async def test_register_anonymous(loop):
    # Register a new anonymous user with no secret
    async with loop.new_session() as s:
        token = await s.register(scheme='anonymous')
        assert token is not None
        user_id = s.user_id
        assert user_id is not None
    
    # Log in again using this token
    async with loop.new_session() as s:
        await s.login(scheme='token', secret=token)

@pytest.mark.asyncio
async def test_register_invalid(loop):
    async with loop.new_session() as s:
        with pytest.raises(Rejected):
            await s.register(scheme='token')
        with pytest.raises(Rejected):
            await s.register(scheme='asdf')
        with pytest.raises(Rejected):
            await s.register(secret='username1')
        with pytest.raises(Rejected):
            await s.register(secret=':password1')
        with pytest.raises(Rejected):
            await s.register()

def simple_encode(s):
    return json.dumps(s).encode('utf-8')

def simple_decode(b):
    return json.loads(b.decode('utf-8'))

@pytest.mark.asyncio
async def test_p2p_topic_publish(loop):
    secret_s1 = random_secret()
    async with loop.new_session() as s1, loop.new_session() as s2:
        await s1.register(secret_s1)
        await s2.register(random_secret())

        user_ids = [s1.user_id, s2.user_id]

        # s1 can send a message after subscribing
        with pytest.raises(Rejected):
            await s1.publish(s2.user_id, simple_encode('hello'))
        await s1.subscribe(s2.user_id)
        assert s1._ChatSession__data_messages.qsize() == 0
        await s1.publish(s2.user_id, simple_encode('hello'))
        await asyncio.sleep(0.1)
        assert s1._ChatSession__data_messages.qsize() == 1
        s1_messages_aiter = s1.messages()
        echo = await s1_messages_aiter.__anext__()
        assert echo.from_user_id == s1.user_id
        assert simple_decode(echo.content) == 'hello'
        assert s1._ChatSession__data_messages.qsize() == 0

        # s2 does not immediately see the message, even after subscribing
        assert s2._ChatSession__data_messages.qsize() == 0
        await s2.subscribe(s1.user_id)
        assert s2._ChatSession__data_messages.qsize() == 0

        # s2 must request message history
        await s2.get_message_history(s1.user_id)
        await asyncio.sleep(0.1)
        assert s2._ChatSession__data_messages.qsize() == 1
        s2_messages_aiter = s2.messages()
        msg = await s2_messages_aiter.__anext__()
        assert msg.from_user_id == echo.from_user_id
        assert msg.id == echo.id
        assert msg.content == echo.content
        assert s2._ChatSession__data_messages.qsize() == 0

        # now that s2 is subscribed, s1's messages will show up
        await s1.publish(s2.user_id, simple_encode('world'))
        echo = await s1.messages().__anext__()
        assert echo.from_user_id == s1.user_id
        assert simple_decode(echo.content) == 'world'
        assert s1._ChatSession__data_messages.qsize() == 0

        await asyncio.sleep(0.1)
        assert s2._ChatSession__data_messages.qsize() == 1
        msg = await s2_messages_aiter.__anext__()
        assert msg.from_user_id == echo.from_user_id
        assert msg.id == echo.id
        assert msg.content == echo.content
        assert s2._ChatSession__data_messages.qsize() == 0

        await s2.publish(s1.user_id, simple_encode('ok!'))
    
    async with loop.new_session() as s1:
        await s1.login(secret_s1)
        await s1.subscribe(user_ids[1])
        await s1.get_message_history(user_ids[1])
        messages_aiter = s1.messages()

        from_user_ids = []
        from_user_ids.append((await messages_aiter.__anext__()).from_user_id)
        from_user_ids.append((await messages_aiter.__anext__()).from_user_id)
        from_user_ids.append((await messages_aiter.__anext__()).from_user_id)

        assert set(user_ids) == set(from_user_ids)

@pytest.mark.asyncio
async def test_group_subscribers_public(loop):
    async with loop.new_session() as a, loop.new_session() as b:
        await a.register(random_secret(), public=simple_encode('first_user'))
        await b.register(random_secret(), public=simple_encode('second_user'))
        topic = await a.new_topic()
        await b.subscribe(topic)
        subscribers = await a.get_subscribed_users(topic)
        assert same_elements_in_lists(
            ['first_user', 'second_user'],
            [simple_decode(s.public) for s in subscribers])
        subscribers = await b.get_subscribed_users(topic)
        assert same_elements_in_lists(
            ['first_user', 'second_user'],
            [simple_decode(s.public) for s in subscribers])

# @pytest.mark.asyncio
# async def test_p2p_subscribers_public(loop):
#     async with loop.new_session() as a, loop.new_session() as b:
#         await a.register(random_secret(), public=simple_encode('first_user'))
#         await b.register(random_secret(), public=simple_encode('second_user'))
#         await a.subscribe(b.user_id)
#         await b.subscribe(a.user_id)
#         subscribers = await a.get_subscribed_users(b.user_id)
#         assert same_elements_in_lists(
#             ['first_user', 'second_user'],
#             [simple_decode(s.public) for s in subscribers])
#         subscribers = await b.get_subscribed_users(topic)
#         assert same_elements_in_lists(
#             ['first_user', 'second_user'],
#             [simple_decode(s.public) for s in subscribers])

@pytest.mark.asyncio
async def test_p2p_topic_public(loop):
    async with loop.new_session() as s:
        await s.register(random_secret(), public=simple_encode('first_user'))
        user_id = s.user_id
    
    async with loop.new_session() as s:
        await s.register(random_secret(), public=simple_encode('second_user'))
        
        await s.subscribe(user_id)
        topic = await s.get_topic_description(user_id)
        assert simple_decode(topic.public) == 'first_user'
        
        [topic] = await s.get_subscribed_topics()
        assert simple_decode(topic.public) == 'first_user'

@pytest.mark.asyncio
async def test_group_topic_public(loop):
    async with loop.new_session() as s:
        await s.register(random_secret(), public=simple_encode('user'))
        name1 = await s.new_topic(public=simple_encode('first_topic'))
        name2 = await s.new_topic(public=simple_encode('second_topic'))
        
        topic1 = await s.get_topic_description(name1)
        assert simple_decode(topic1.public) == 'first_topic'
        topic2 = await s.get_topic_description(name2)
        assert simple_decode(topic2.public) == 'second_topic'

        topics = dict([(t.topic, simple_decode(t.public))
            for t in await s.get_subscribed_topics()])
        assert len(topics) == 2
        assert topics[name1] == 'first_topic'
        assert topics[name2] == 'second_topic'

@pytest.mark.asyncio
async def test_update_profile(loop):
    async with loop.new_session() as s:
        await s.register(random_secret(), public=simple_encode('hello'))
        profile = await s.get_profile()
        assert simple_decode(profile.public) == 'hello'

        await s.set_profile(public=simple_encode('world'))
        profile = await s.get_profile()
        assert simple_decode(profile.public) == 'world'

@pytest.mark.asyncio
async def test_p2p_topic_last_message_timestamp(loop):
    async with loop.new_session() as s:
        await s.register(random_secret())
        topic_name = s.user_id

    async with loop.new_session() as s:
        await s.register(random_secret())
        await s.subscribe(topic_name)

        [sub] = await s.get_subscribed_topics()
        t = sub.last_message_timestamp
        topic = await s.get_topic_description(topic_name)
        assert topic.last_message_timestamp == sub.last_message_timestamp
        
        now = dt.datetime.now()
        await asyncio.sleep(0.1)
        await s.publish_str(topic_name, 'hello')
        [sub] = await s.get_subscribed_topics()
        assert t < sub.last_message_timestamp
        assert now < sub.last_message_timestamp
        t = sub.last_message_timestamp
        topic = await s.get_topic_description(topic_name)
        assert topic.last_message_timestamp == sub.last_message_timestamp

        now = dt.datetime.now()
        await asyncio.sleep(0.1)
        await s.publish_str(topic_name, 'world')
        [sub] = await s.get_subscribed_topics()
        assert t < sub.last_message_timestamp
        assert now < sub.last_message_timestamp
        t = sub.last_message_timestamp
        topic = await s.get_topic_description(topic_name)
        assert topic.last_message_timestamp == sub.last_message_timestamp

@pytest.mark.asyncio
async def test_group_topic_last_message_timestamp(loop):
    async with loop.new_session() as s:
        await s.register(random_secret())
        topic_name = await s.new_topic()

        [sub] = await s.get_subscribed_topics()
        t = sub.last_message_timestamp
        topic = await s.get_topic_description(topic_name)
        assert topic.last_message_timestamp == sub.last_message_timestamp
        
        now = dt.datetime.now()
        await asyncio.sleep(0.1)
        await s.publish_str(topic_name, 'hello')
        [sub] = await s.get_subscribed_topics()
        assert t < sub.last_message_timestamp
        assert now < sub.last_message_timestamp
        t = sub.last_message_timestamp
        topic = await s.get_topic_description(topic_name)
        assert topic.last_message_timestamp == sub.last_message_timestamp

        now = dt.datetime.now()
        await asyncio.sleep(0.1)
        await s.publish_str(topic_name, 'world')
        [sub] = await s.get_subscribed_topics()
        assert t < sub.last_message_timestamp
        assert now < sub.last_message_timestamp
        t = sub.last_message_timestamp
        topic = await s.get_topic_description(topic_name)
        assert topic.last_message_timestamp == sub.last_message_timestamp

@pytest.mark.asyncio
async def test_find_users_by_tags(loop):
    async with loop.new_session() as a, loop.new_session() as b:
        tag = os.urandom(8).hex()
        await a.register(random_secret(), tags=[tag])
        await b.register(random_secret())
        
        # A doesn't find himself in results
        users = await a.find_users(tag)
        assert len(users) == 0

        # B finds A in results
        [user] = await b.find_users(tag)
        assert user.user_id == a.user_id

        # B doesn't find A if the search query is wrong
        users = await b.find_users(os.urandom(8).hex())
        assert len(users) == 0

@pytest.mark.asyncio
async def test_find_topics_by_tags(loop):
    async with loop.new_session() as a, loop.new_session() as b:
        await a.register(random_secret())
        await b.register(random_secret())
        
        tag = os.urandom(8).hex()
        topic = await a.new_topic(tags=[tag])

        [found_topic] = await a.find_topics(tag)
        assert found_topic.topic == topic

        [found_topic] = await b.find_topics(tag)
        assert found_topic.topic == topic

@pytest.mark.asyncio
async def test_find_topics_and_users_with_same_tags(loop):
    async with loop.new_session() as a, loop.new_session() as b:
        tag = os.urandom(8).hex()
        await a.register(random_secret(), tags=[tag])
        await b.register(random_secret())
        topic = await a.new_topic(tags=[tag])

        # A doesn't find himself in results
        found_users = await a.find_users(tag)
        assert len(found_users) == 0
        [found_topic] = await a.find_topics(tag)
        assert found_topic.topic == topic

        [found_user] = await b.find_users(tag)
        assert found_user.user_id == a.user_id
        [found_topic] = await b.find_topics(tag)
        assert found_topic.topic == topic

@pytest.mark.asyncio
async def test_delete_topic(loop):
    b_secret = random_secret()
    async with loop.new_session() as a, loop.new_session() as b:
        await a.register(random_secret())
        await b.register(b_secret)
        
        topic = await a.new_topic()
        await b.subscribe(topic)
        assert len(await b.get_subscribed_topics()) == 1
        await a.delete_topic(topic)
        assert len(await b.get_subscribed_topics()) == 0
        
        with pytest.raises(Rejected):
            await b.subscribe(topic)

@pytest.mark.asyncio
async def test_permissions_owner_cannot_leave(loop):
    async with loop.new_session() as a, loop.new_session() as b:
        await a.register(random_secret())
        await b.register(random_secret())

        topic = await a.new_topic()
        await b.subscribe(topic)

        with pytest.raises(Rejected):  # The only owner can't leave the topic
            await a.leave(topic, unsubscribe=True)

@pytest.mark.asyncio
async def test_permissions_owner_cannot_leave_before_new_owner_accepts(loop):
    async with loop.new_session() as a, loop.new_session() as b:
        await a.register(random_secret())
        await b.register(random_secret())

        topic = await a.new_topic()
        await b.subscribe(topic)

        # Transfer ownership, and try leaving before B accepts
        await a.set_permissions(topic, b.user_id, "JRWPASDO")
        with pytest.raises(Rejected):
            await a.leave(topic, unsubscribe=True)

@pytest.mark.asyncio
async def test_permissions_non_owner_cannot_take_ownership(loop):
    async with loop.new_session() as a, loop.new_session() as b:
        await a.register(random_secret())
        await b.register(random_secret())

        topic = await a.new_topic()
        await b.subscribe(topic)

        # A, the current owner, has not given ownership to B yet
        with pytest.raises(Rejected):
            await b.set_permissions(topic, None, "JRWPASDO")

@pytest.mark.asyncio
async def test_permissions_owner_can_leave_after_new_owner_accepts(loop):
    async with loop.new_session() as a, loop.new_session() as b:
        await a.register(random_secret())
        await b.register(random_secret())

        topic = await a.new_topic()
        await b.subscribe(topic)

        # Transfer ownership
        await a.set_permissions(topic, b.user_id, "JRWPASDO")

        # Accept the transfer of ownership
        await b.set_permissions(topic, None, "JRWPASDO")
        await a.leave(topic, unsubscribe=True)
        assert len(await a.get_subscribed_topics()) == 0

@pytest.mark.asyncio
async def test_subscribe_and_attach(loop):
    async with loop.new_session() as a:
        await a.register(random_secret())

        b_secret = random_secret()
        async with loop.new_session() as b:
            await b.register(b_secret)

            # 'a' makes a new topic
            topic = await a.new_topic()
            [subscriber] = await a.get_subscribed_users(topic)
            assert subscriber.user_id == a.user_id
            
            # 'b' subscribes to it
            await b.subscribe(topic)
            users = await a.get_subscribed_users(topic)
            assert same_elements_in_lists(
                [a.user_id, b.user_id],
                [u.user_id for u in users])
            users = await b.get_subscribed_users(topic)
            assert same_elements_in_lists(
                [a.user_id, b.user_id],
                [u.user_id for u in users])
            [subscription] = await a.get_subscribed_topics()
            assert subscription.topic == topic
            [subscription] = await b.get_subscribed_topics()
            assert subscription.topic == topic

        # 'b' disconnects, and connects again without subscribing
        async with loop.new_session() as b:
            await b.login(b_secret)

            # 'a' can still see that 'b' is attached, though
            # not currently subscribed to notifications
            users = await a.get_subscribed_users(topic)
            assert same_elements_in_lists(
                [a.user_id, b.user_id],
                [u.user_id for u in users])
            
            # 'b' no longer gets the topic back in subscriptions
            [subscription] = await a.get_subscribed_topics()
            assert subscription.topic == topic
            [subscription] = await b.get_subscribed_topics()
            assert subscription.topic == topic

@pytest.mark.asyncio
async def test_group_recv_and_read(loop):
    async with loop.new_session() as a, loop.new_session() as b:
        await a.register(random_secret())
        await b.register(random_secret())

        # Send two messages as A
        topic = await a.new_topic()
        await b.subscribe(topic)
        await a.publish(topic, simple_encode('x'))
        await a.publish(topic, simple_encode('y'))

        # Consume messages as B
        b_messages_iter = b.messages()
        await asyncio.sleep(0.1)
        msg = await b_messages_iter.__anext__()
        assert msg.id == 1
        msg = await b_messages_iter.__anext__()
        assert msg.id == 2

        # Check topic descriptions now, as both A and B
        topic_description = await a.get_topic_description(topic)
        assert topic_description.read_message_id == 2
        assert topic_description.received_message_id == 2
        assert topic_description.last_message_id == 2
        topic_description = await b.get_topic_description(topic)
        assert topic_description.read_message_id == 0
        assert topic_description.received_message_id == 0
        assert topic_description.last_message_id == 2

        # Let B receive and read msg 1
        await b.notify_received(topic, 1)
        await b.notify_read(topic, 1)
        
        # Check topic descriptions again, as both A and B
        await asyncio.sleep(0.1)
        topic_description = await a.get_topic_description(topic)
        assert topic_description.read_message_id == 2
        assert topic_description.received_message_id == 2
        assert topic_description.last_message_id == 2
        topic_description = await b.get_topic_description(topic)
        assert topic_description.read_message_id == 1
        assert topic_description.received_message_id == 1
        assert topic_description.last_message_id == 2

        # Let B receive msg 2 (without reading it)
        await b.notify_received(topic, 2)
        
        # Check topic descriptions again, as both A and B
        await asyncio.sleep(0.1)
        topic_description = await a.get_topic_description(topic)
        assert topic_description.read_message_id == 2
        assert topic_description.received_message_id == 2
        assert topic_description.last_message_id == 2
        topic_description = await b.get_topic_description(topic)
        assert topic_description.read_message_id == 1
        assert topic_description.received_message_id == 2
        assert topic_description.last_message_id == 2