from .monkeypatch import patch
from .trace import TraceSegment, get_trace_info, parse_trace_info

global_segment = TraceSegment()

__all__ = ['patch', 'global_segment']

__version__ = '0.0.2'
