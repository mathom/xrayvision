import boto3
import json
import logging
import random
import time


logger = logging.getLogger(__name__)


class TraceException(Exception):
    pass


class TraceSegment(object):
    '''
    Trace segments are spans of time that are used to
    measure execution time for sections of code.

    They can contain subsegments with more detailed information.
    '''

    def __init__(self, name, trace_id=None):
        self._id = self.random_id()
        self.name = name
        self.trace_id = trace_id

        self.start_time = time.time()
        self.end_time = None

        self.closed = False
        self.sampled = None

        self.subsegments = []

        if not self.trace_id:
            self.trace_id = self.random_trace_id()

    def random_id(self):
        return '{0:016x}'.format(random.randrange(2**64))

    def random_trace_id(self):
        return '1-{0:08x}-{1:024x}'.format(int(self.start_time),
                                           random.randrange(2**96))

    def __enter__(self):
        if self.closed:
            raise TraceException('TraceSegment already closed, cannot use it again')

        self.start_time = time.time()

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self.closed:
            raise TraceException('TraceSegment already closed, cannot close it again')

        self.closed = True
        self.end_time = time.time()

        self.submit()

    def is_sampled(self):
        # TODO implement sampling algorithm here
        if self.sampled is not None:
            return self.sampled
        else:
            return True

    def get_segments(self):
        segments = []

        segments.append(json.dumps({
            'name': self.name,
            'id': self._id,
            'trace_id': self.trace_id,
            'start_time': self.start_time,
            'end_time': self.end_time
        }))

        segments.extend(x.get_document() for x in self.subsegments)

        return segments

    def submit(self):
        if not self.is_sampled():
            logger.debug('Skipping TraceSegment %s submit because of sampling', self.trace_id)
            return

        xray = boto3.client('xray')
        xray.put_trace_segments(TraceSegmentDocuments=self.get_segments())
        logger.debug('Submitted TraceSegment %s', self.trace_id)
