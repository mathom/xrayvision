from xrayvision import global_segment
from xrayvision.monkeypatch import mark_patched

import requests
#import urlparse
import wrapt


def patch():
    wrapt.wrap_function_wrapper('requests', 'Session.request', _wrapped_request)
    mark_patched('requests')


def _wrapped_request(func, instance, args, kwargs):

    method = kwargs.get('method') or args[0]
    url = kwargs.get('url') or args[1]
    headers = kwargs.get('headers')

    #url_parts = urlparse.urlparse(url)

    with global_segment.add_subsegment('requests') as seg:
        http = {
            'request': {
                'method': method,
                'url': url
            }
        }

        seg.http = http
        seg.namespace = 'remote'

        try:
            response = func(*args, **kwargs)

            http['response'] = {
                'status': response.status_code,
                'content_length': response.headers.get('content-length', 0)
            }

            return response

        except:
            seg.add_exception()
            raise

        finally:
            pass


__all__ = ['patch']
