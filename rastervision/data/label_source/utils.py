import json
from typing import Tuple

import numpy as np
from PIL import ImageColor

import rastervision as rv
from rastervision.core.box import Box
from rastervision.data import (ChipClassificationLabels, ObjectDetectionLabels)
from rastervision.utils.files import file_to_str


def color_to_triple(color: str) -> Tuple[int, int, int]:
    """Given a PIL ImageColor string, return a triple of integers
    representing the red, green, and blue values.

    Args:
         color: A PIL ImageColor string

    Returns:
         An triple of integers

    """
    if color is None:
        r = np.random.randint(0, 0x100)
        g = np.random.randint(0, 0x100)
        b = np.random.randint(0, 0x100)
        return (r, g, b)
    else:
        return ImageColor.getrgb(color)


def color_to_integer(color: str) -> int:
    """Given a PIL ImageColor string, return a packed integer.

    Args:
         color: A PIL ImageColor string

    Returns:
         An integer containing the packed RGB values.

    """
    triple = color_to_triple(color)
    r = triple[0] * (1 << 16)
    g = triple[1] * (1 << 8)
    b = triple[2] * (1 << 0)
    integer = r + g + b
    return integer


def rgb_to_int_array(rgb_array):
    r = np.array(rgb_array[:, :, 0], dtype=np.uint32) * (1 << 16)
    g = np.array(rgb_array[:, :, 1], dtype=np.uint32) * (1 << 8)
    b = np.array(rgb_array[:, :, 2], dtype=np.uint32) * (1 << 0)
    return r + g + b


def check_uri_type(uri):
    if not isinstance(uri, str):
        raise rv.ConfigError(
            'uri set with "with_uri" must be of type str, got {}'.format(
                type(uri)))
