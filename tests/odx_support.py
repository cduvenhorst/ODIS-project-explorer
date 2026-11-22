"""Helpers for the ODX export tests; all names are invented."""
import xml.etree.ElementTree as ET

from odx_export.context import PoolContext


def context(objects, pool_id='0.0.0@L.sd', **kwargs):
    """Build a PoolContext from {key: (type name, object)} in the given order."""
    return PoolContext(pool_id,
                       {key: value[1] for key, value in objects.items()},
                       {key: value[0] for key, value in objects.items()},
                       **kwargs)


def xml(element):
    return ET.tostring(element, encoding='unicode')
