from monkeypatch import patch
from trace import TraceSegment

global_segment = TraceSegment()

__all__ = ['patch', 'global_segment']

__version__ = '0.0.1'
