import os
import asyncio
import threading
from . import session

class ChatLoop(object):
    """
    Responsible for creating an `asyncio` event loop in a background thread
    that chat sessions can share and for creating new chat sessions connected
    to that thread and event loop.
    """

    def __init__(self, host=None, port=None):
        self.__host = host
        self.__port = port
    
    # Flask integration -- see app/__init__.py
    def init_app(self, app):
        self.init(app.config['CHAT_HOST'], app.config['CHAT_PORT'])
    
    def init(self, host, port):
        self.__host = host
        self.__port = port
    
    def init_from_env(self):
        self.init(os.environ['CHAT_HOST'], os.environ['CHAT_PORT'])
    
    def __run_event_loop(self):
        """ Runs in a background thread """
        asyncio.set_event_loop(self.__loop)
        self.__loop.run_forever()
    
    __loop = None
    __new_session_lock = threading.Lock()
    __thread = None

    def new_session(self) -> session.ChatSession:
        """
        Open a new session connected to the chat server using
        connection details provided at initialization time.
        """

        # On the first time, start the background thread and event loop
        print('getting lock')
        with self.__new_session_lock:
            print('in lock')
            if self.__loop is None:
                print('loop is none')
                self.__loop = asyncio.new_event_loop()
                print('created new loop')
                self.__thread = threading.Thread(target=self.__run_event_loop)
                print('created new thread')
                self.__thread.start()
                print('started new thread')

        # Return a new session
        s = session.ChatSession(
            self.__host,
            self.__port,
            self.__loop)
        return s
    
    def stop(self):
        if self.__loop is not None:
            self.__loop.call_soon_threadsafe(self.__loop.stop)
        if self.__thread is not None:
            self.__thread.join()