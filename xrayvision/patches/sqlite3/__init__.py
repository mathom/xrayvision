'''
Wrap some important functions in sqlite3 so we can instrument them.
'''

from xrayvision.monkeypatch import mark_patched, is_patched


_old_connect = sqlite3.connect


def patch(module):
    module
