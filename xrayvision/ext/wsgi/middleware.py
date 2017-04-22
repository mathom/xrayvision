from xrayvision.trace import TraceSegment


class XrayMiddleware(object):
    '''Wrap a WSGI app to provide Xray stats'''

    def __init__(self, app, name=None):
        self.app = app
        self.name = name

    def __call__(self, environ, start_response):
        '''Call the app handler'''

        print environ
        path_info = environ['PATH_INFO']
        trace_id = environ.get('HTTP_X_AMZN_TRACE_ID')
        trace_root = None
        trace_parent = None
        sampled = None

        name = self.name or environ['SCRIPT_NAME'] or environ['SERVER_SOFTWARE']

        trace = TraceSegment(name, trace_root)

        if trace_id:
            for entry in trace_id.split(';'):
                name, val = entry.split('=')
                name = name.lower()
                if name == 'sampled':
                    sampled = val
                elif name == 'root':
                    trace_root = val
                elif name == 'parent':
                    trace_parent = val

        if sampled == '1':
            trace.sampled = True
        elif sampled == '0':
            trace.sampled = False

        try:
            app_iter = self.app(environ, start_response)
            for item in app_iter:
                yield item

        except:
            # TODO: record this exception
            raise

        finally:
            trace.close()

        if hasattr(app_iter, 'close'):
            app_iter.close()
