import boto3
import json
import logging
import os
import random
import sys
import time
import traceback


logger = logging.getLogger(__name__)


class TraceException(Exception):
    pass


def random_64bit_id():
    return '{0:016x}'.format(random.randrange(2**64))


def get_loaded_modules():
    '''Returns an array of paths to all loaded modules and libs'''
    blacklist = set(sys.builtin_module_names)
    result = []
    for name, module in sys.modules.items():
        if module and name not in blacklist:
            path = getattr(module, '__file__', None)
            if path:
                result.append(path)
    return sorted(result)


def get_current_exception():
    '''Create an exception dict in xray format'''

    etype, value, tb = sys.exc_info()

    if etype is None:
        return None

    result = {
        'id': random_64bit_id(),
        'message': str(value),
        'type': etype.__name__,
        'stack': []
    }

    for filename, line, func, text in traceback.extract_tb(tb):
        result['stack'].append({
            'path': filename,
            'line': line,
            'label': func
        })

    result['stack'].reverse()

    return result


def parse_trace_info(trace_value):
    '''Parse the keys out of an xray trace string and return (root, parent, sampled) tuple.'''
    trace_root = None
    trace_parent = None
    sampled = None

    if trace_value:
        for entry in trace_value.split(';'):
            key, val = entry.split('=')
            if key == 'Sampled':
                sampled = val
            elif key == 'Root':
                trace_root = val
            elif key == 'Parent':
                trace_parent = val

    return (trace_root, trace_parent, sampled)


def get_trace_info():
    '''Return a tuple of (root, parent, sampled) if found in the environment.'''

    if '_X_AMZN_TRACE_ID' in os.environ:
        return parse_trace_info(os.environ['_X_AMZN_TRACE_ID'])
    else:
        return (None, None, None)


class TraceSegment(object):
    '''
    Trace segments are spans of time that are used to
    measure execution time for sections of code.

    They can contain subsegments with more detailed information.

    A global instance of the root segment is already created for you in xrayvision.
    '''

    def __init__(self, subsegment=False):
        self.closed = False
        self.is_subsegment = subsegment

    def begin(self, name, trace_id=None, parent_id=None):
        self.closed = False

        self._id = random_64bit_id()
        self.name = name
        self.trace_id = trace_id
        self.parent_id = parent_id

        self.start_time = time.time()
        self.end_time = None

        self.sampled = None

        self.error = None
        self.throttle = None
        self.fault = None
        self.cause = None
        self.namespace = None

        self.http = {}

        self.aws = None  # TODO: auto populate this thing

        self.subsegments = []

        self.annotations = {}
        self.metadata = {}

        if not self.trace_id:
            self.trace_id = self.random_trace_id()

        if self.is_subsegment:
            logger.debug('Adding new subsegment %s %s to %s',
                         name, self._id, self.parent_id)
        else:
            logger.debug('Created new TraceSegment %s %s %s',
                         name, self._id, self.trace_id)

        return self

    def random_trace_id(self):
        return '1-{0:08x}-{1:024x}'.format(int(self.start_time),
                                           random.randrange(2**96))

    def add_subsegment(self, name):
        '''Create and begin a new subsegment that is nested inside this segment'''
        subsegment = TraceSegment(True)
        self.subsegments.append(subsegment)
        return subsegment.begin(name, trace_id=self.trace_id, parent_id=self._id)


    def __enter__(self, *args, **kwargs):
        if self.closed:
            raise TraceException('TraceSegment already closed, cannot use it again')

        return self

    def __exit__(self, *args):
        # TODO: capture exceptions here?
        self.close()

    def close(self):
        if self.closed:
            raise TraceException('TraceSegment already closed, cannot close it again')

        self.closed = True
        self.end_time = time.time()

        if not self.is_subsegment:
            self.submit()

    def is_sampled(self):
        # TODO implement sampling algorithm here
        if self.sampled is not None:
            return self.sampled
        else:
            return True

    def add_annotation(self, key, value):
        '''Annotations are indexed and searchable/filterable in AWS'''
        self.annotations[key] = value

    def add_metadata(self, key, value):
        '''Metadata is non-indexed data associated with the trace'''
        self.metadata[key] = value

    def add_http_status(self, status):
        '''Set the segment fault/error status based on HTTP status'''
        if status >= 500:
            self.fault = True
        elif status == 409:
            self.throttle = True
        elif status >= 400:
            self.error = True

    def add_exception(self):
        '''Add an exception to the current trace.
        If http data exists, use the status from there.'''

        if self.http and 'response' in self.http:
            status = self.http['response'].get('status', 0)
            if status >= 400:
                self.add_http_status(status)
            else:
                self.fault = True
        else:
            self.fault = True  # general exceptions

        if not self.cause:
            self.cause = {}

        exception = get_current_exception()
        if exception:
            self.cause['working_directory'] = os.getcwd()
            #self.cause['paths'] = get_loaded_modules()
            self.cause.setdefault('exceptions', [])
            self.cause['exceptions'].append(get_current_exception())

    def get_document(self):
        '''Returns the dict representing this trace segment'''
        result = {
            'name': self.name,
            'id': self._id,
            'trace_id': self.trace_id,
            'start_time': self.start_time,
            'end_time': self.end_time
        }

        fields = (
            'annotations',
            'cause',
            'error',
            'fault',
            'http',
            'metadata',
            'namespace',
            'parent_id',
            'throttle',
        )

        for field in fields:
            if getattr(self, field) is not None:
                result[field] = getattr(self, field)

        if self.subsegments:
            result['subsegments'] = [x.get_document() for x in self.subsegments]

        return result

    def get_segments(self):
        segments = []

        segments.append(json.dumps(self.get_document()))

        return segments

    def submit(self):
        if not self.is_sampled():
            logger.debug('Skipping TraceSegment %s submit because of sampling', self.trace_id)
            return

        xray = boto3.client('xray')
        result = xray.put_trace_segments(TraceSegmentDocuments=self.get_segments())
        logger.debug('Submitted TraceSegment %s', self.trace_id)

        if result['UnprocessedTraceSegments']:
            logger.warning('Unprocessed trace segments: %s', result['UnprocessedTraceSegments'])
