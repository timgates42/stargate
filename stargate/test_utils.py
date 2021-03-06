import pyramid_zcml
import eventlet
import logging
from eventlet import Queue, greenthread, hubs, wsgi
from pyramid import testing
from pyramid.exceptions import NotFound
from pyramid.httpexceptions import HTTPNotFound
from StringIO import StringIO

from stargate import WebSocketView

class Root(object):
    pass

def get_root(request):
    return Root()

def not_found(context, request):
    assert(isinstance(context, NotFound))
    return HTTPNotFound()


class Fixture(object):
    """Use fixture to setup a server once for a module"""

    def __init__(self, zcml_file=None, root_factory=None, views=None, routes=None):
        """
        :param zcml_file: Path (or spec) of a zcml file
        :param views: List of dicts suitable as kwargs to
            :meth:`pyramid.configuration.Configurator.add_view`
        :param routes: List of tuples of (name, path, kwargs) to pass to
            :meth:`pyramid.configuration.Configurator.add_route`
        """
        self.zcml = zcml_file
        self.root_factory = root_factory
        self.views = views or []
        self.routes = routes or []
        self.config = testing.setUp()

    def start_server(self, module=None):
        config = self.config
        config._set_root_factory(self.root_factory or get_root)
        config_logger = logging.getLogger("config")
        config_logger.setLevel(logging.INFO)
        if self.zcml:
            config.include(pyramid_zcml)
            config.load_zcml(self.zcml)
        for name, path, kw in self.routes:
            config.add_route(name, path, **kw)
        for view_kwargs in self.views:
            config.add_view(**view_kwargs)
        # Add a not found view as setup_registry won't have been called
        config.add_view(view=not_found, context=NotFound)
        config.end()
        self.config = config
        self.logfile = StringIO()
        self.killer = None
        self._spawn_server()
        eventlet.sleep(0.3)

    def _spawn_server(self, **kwargs):
        """Spawns a new wsgi server with the given arguments.
        Sets self.port to the port of the server, and self.killer is the greenlet
        running it.

        Kills any previously-running server.
        """
        if self.killer:
            greenthread.kill(self.killer)
            eventlet.sleep(0)
        app = self.config.make_wsgi_app()
        new_kwargs = dict(max_size=128,
                          log=self.logfile)
        new_kwargs.update(kwargs)

        sock = eventlet.listen(('localhost', 0))

        self.port = sock.getsockname()[1]
        self.killer = eventlet.spawn_n(wsgi.server, sock, app, **new_kwargs)

    def clear_up(self, module=None):
        greenthread.kill(self.killer)
        eventlet.sleep(0)
        try:
            hub = hubs.get_hub()
            num_readers = len(hub.get_readers())
            num_writers = len(hub.get_writers())
            assert num_readers == num_writers == 0
        except AssertionError:
            print "ERROR: Hub not empty"
            print debug.format_hub_timers()
            print debug.format_hub_listeners()

        eventlet.sleep(0)

class WSTestGenerator(WebSocketView):

    def handle_websocket(self, ws):
        self._ws = ws
        return super(RangeWebsocket, self)

    def handler(self, ws):
        self.queue = Queue()
        while True:
            m = ws.wait()
#            import ipdb; ipdb.set_trace()
            if m is None:
                break
            self.queue.put(m)

class WSTestCase(object):

    def setUp(self):
        pass

    def tearDown(self):
        pass
        