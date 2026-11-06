"""Explicit bounds for the documented M-EVI parameter inventory."""
import json
import math
from importlib.resources import files
from types import MappingProxyType

CATALOG = tuple(json.loads(files(__package__).joinpath('catalog.json').read_text(encoding='utf-8')))
BY_ADDRESS = MappingProxyType({row['address']: row for row in CATALOG})


def encode_parameter(address, value):
    row = BY_ADDRESS.get(address)
    if row is None or row['access'] not in ('service', 'setpoint'):
        raise ValueError('Parameter is reserved, ambiguous or not writable through this interface')
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Parameter requires a finite integer')
    low, high = row['bounds']
    if value != int(value) or not low <= value <= high:
        raise ValueError(f'Parameter raw value must be an integer in {low}..{high}')
    return int(value) & 0xFFFF
