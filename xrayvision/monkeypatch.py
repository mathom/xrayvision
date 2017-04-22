import logging
import importlib
import sys


class PatchException(Exception):
    pass


def is_patched(module_name):
    if module_name not in sys.modules:
        logging.warning('{0} not imported yet'.format(module_name))
        return False

    return getattr(sys.modules[module_name], '__xrayv_patched', False)


def mark_patched(module_name):
    if module_name not in sys.modules:
        logging.warning(
            '{0} not imported, cannot mark as patched'.format(module_name))
        return

    setattr(sys.modules[module_name], '__xrayv_patched', True)


def patch(module_name):
    if is_patched(module_name):
        return

    patch_path = 'xrayvision.patches.{0}'.format(module_name)

    try:
        patcher = importlib.import_module(patch_path)
    except ImportError:
        message = '{0} is not supported in xrayvision'.format(module_name)
        logging.exception(message)
        raise PatchException(message)

    patcher.patch()

    if not is_patched(module_name):
        raise PatchException('{0} was not patched successfully'.format(module_name))
