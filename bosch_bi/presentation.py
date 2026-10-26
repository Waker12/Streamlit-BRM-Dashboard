"""Shared display rules; never round source calculations or CSV downloads."""
from numbers import Real
import pandas as pd
from pandas.api.types import is_numeric_dtype

SHOPEE = '#EE4D2D'
LAZADA = '#1468D4'
MARKETPLACE_COLORS = {'Shopee': SHOPEE, 'Lazada': LAZADA}


def number(value, places=2, signed=False):
    if value is None or pd.isna(value):
        return '—'
    return format(value, ('+' if signed else '') + f',.{places}f')


def numeric_display(frame):
    """Recover numeric object columns without converting source IDs or dates."""
    result = frame.copy().infer_objects()
    for col in result:
        values = result[col].dropna()
        if not values.empty and values.map(lambda v: isinstance(v, Real) and not isinstance(v, bool)).all():
            result[col] = pd.to_numeric(result[col], errors='coerce')
    return result


def numeric_columns(frame):
    return [c for c in frame if is_numeric_dtype(frame[c]) and frame[c].dtype.kind != 'b']


def marketplace_theme(platform=None):
    return {'Shopee': [SHOPEE, '#FFD2C5', '#A82B13', '#FF9979'],
            'Lazada': [LAZADA, '#CBDFFA', '#123D83', '#6CA7F3']}.get(
                platform, ['#007BC0', '#CBD5DF', '#E20015', '#20A4A0'])
