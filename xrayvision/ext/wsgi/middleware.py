from xrayvision import global_segment, get_trace_info, parse_trace_info


class XRayMiddleware(object):
    '''Wrap a WSGI app to provide Xray stats'''

    def __init__(self, app, name=None, prefer_lambda_trace=False):
        self.app = app
        self.name = name
        self.prefer_lambda_trace = prefer_lambda_trace

    def __call__(self, environ, start_response):
        '''Call the app handler'''

        trace_id = environ.get('HTTP_X_AMZN_TRACE_ID')
        trace_root = None
        trace_parent = None
        sampled = None

        # in lambda, this will be sourced from the environment
        if self.prefer_lambda_trace:
            trace_root, trace_parent, sampled = get_trace_info()

        if not trace_root:
            trace_root, trace_parent, sampled = parse_trace_info(trace_id)

        name = (self.name or environ.get('SCRIPT_NAME')
                or environ.get('SERVER_SOFTWARE') or 'wsgi')

        trace = global_segment.begin(name, trace_root, trace_parent)

        if sampled == '1':
            trace.sampled = True
        elif sampled == '0':
            trace.sampled = False

        url = '{0}://{1}{2}'.format(environ['wsgi.url_scheme'],
                                    environ['HTTP_HOST'],
                                    environ['PATH_INFO'])

        if environ.get('QUERY_STRING'):
            url += '?' + environ['QUERY_STRING']

        http = {
            'request': {
                'method': environ['REQUEST_METHOD'],
                'url': url,
                'user_agent': environ['HTTP_USER_AGENT'],
                'client_ip': environ['REMOTE_ADDR']
            }
        }

        trace.http = http

        # record header stuff in metadata
        for name, value in environ.items():
            if name.startswith('HTTP_'):
                trace.add_metadata(name, value)

        trace.add_annotation('server_protocol', environ['SERVER_PROTOCOL'])

        # helper to capture response information
        def _start_response(status, headers):
            http.setdefault('response', {})
            response = http['response']

            response['status'] = int(status.split()[0])
            hdict = {x[0]: x[1] for x in headers}
            if 'Content-Length' in hdict:
                response['content_length'] = int(hdict['Content-Length'])

            return start_response(status, headers)

        if environ.get('HTTP_X_FORWARDED_FOR'):
            http['request']['x_forwarded_for'] = environ['HTTP_X_FORWARDED_FOR']

        try:
            app_iter = self.app(environ, _start_response)
            for item in app_iter:
                yield item

            status = http.get('response', {}).get('status', 0)
            trace.add_http_status(status)

        except:
            trace.add_exception()
            raise

        finally:
            trace.close()

        if hasattr(app_iter, 'close'):
            app_iter.close()
