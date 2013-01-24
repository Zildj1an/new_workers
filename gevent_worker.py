from gevent import monkey
monkey.patch_all()

import random
import signal
import gevent
import gevent.pool
from gevent.event import Event
import time
from functools import wraps
from base_worker import BaseWorker


def safe_wrap(func):
    """
    This safety wrapper wraps 100% CPU-bound methods to have at least one
    point where a context-switch is allowed to take place.  This makes sure
    that the main worker process does not freeze when only CPU-bound methods
    are executed, effectively making it impossible to cancel using Ctrl+C.
    """
    @wraps(func)
    def _wrapper(*args, **kwargs):
        time.sleep(0)  # ensure that at least one context-switch is possible before calling func
        return func(*args, **kwargs)
    return _wrapper


class GeventWorker(BaseWorker):

    def __init__(self, num_processes=1):
        self._pool = gevent.pool.Pool(num_processes)
        self._events = {}

    def install_signal_handlers(self):
        # Enabling the following line to explicitly set SIGINT yields very
        # weird behaviour: can anybody explain?
        # gevent.signal(signal.SIGINT, signal.default_int_handler)
        gevent.signal(signal.SIGTERM, signal.default_int_handler)

    def get_ident(self):
        return id(gevent.getcurrent())

    def unregister_child(self, child):
        print '==> Unregistering {}'.format(id(child))
        del self._events[child]

    def spawn_child(self):
        """Forks and executes the job."""
        event = Event()
        child_greenlet = self._pool.spawn(self.main_child, event)
        self._events[child_greenlet] = event
        child_greenlet.link(self.unregister_child)

    def main_child(self, event):
        #safe_wrap(self.fake))
        event.clear()
        time.sleep(random.randint(0, 10))
        event.set()

        time.sleep(0)  # TODO: Required to avoid "blocking" by CPU-bound jobs
        try:
            self.fake()
        finally:
            event.clear()

    def terminate_idle_children(self):
        #print "TODO: Should find all children that are waiting for Redis' BLPOP command."
        print "Find all children that are waiting for Redis' BLPOP command..."
        for child_greenlet, busy_event in self._events.items():
            if not busy_event.is_set():
                print '==> Killing {}'.format(id(child_greenlet))
                child_greenlet.kill()
            else:
                print '==> Waiting for {} (still busy)'.format(id(child_greenlet))

    def wait_for_children(self):
        print 'waiting for children to finish gracefully...'
        self._pool.join()
        print 'YIPPY!'

    def kill_children(self):
        print 'killing all children...'
        self._pool.kill()
        print 'MWHUAHAHAHAHA!'
        self.wait_for_children()


if __name__ == '__main__':
    gw = GeventWorker(40)
    gw.work()
