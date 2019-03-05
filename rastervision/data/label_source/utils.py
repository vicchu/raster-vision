import json
from typing import Tuple

import numpy as np
from PIL import ImageColor

import rastervision as rv
from rastervision.core.box import Box
from rastervision.data import (ChipClassificationLabels, ObjectDetectionLabels)
from rastervision.utils.files import file_to_str


def geojson_to_chip_classification_labels(geojson_dict,
                                          crs_transformer,
                                          extent=None):
    """Convert GeoJSON to ChipClassificationLabels.

    If extent is given, only labels that intersect with the extent are returned.

    Args:
        geojson_dict: dict in GeoJSON format
        crs_transformer: used to convert map coords in geojson to pixel coords
            in labels object
        extent: Box in pixel coords

    Returns:
       ChipClassificationLabels
    """
    features = geojson_dict['features']

    labels = ChipClassificationLabels()

    extent_shape = None
    if extent:
        extent_shape = extent.to_shapely()

    def polygon_to_label(polygon, crs_transformer):
        polygon = [crs_transformer.map_to_pixel(p) for p in polygon]
        xmin, ymin = np.min(polygon, axis=0)
        xmax, ymax = np.max(polygon, axis=0)
        cell = Box(ymin, xmin, ymax, xmax)

        if extent_shape and not cell.to_shapely().intersects(extent_shape):
            return

        properties = feature['properties']
        class_id = properties['class_id']
        scores = properties.get('scores')

        labels.set_cell(cell, class_id, scores)

    for feature in features:
        # This was added to handle empty GeometryCollections which appear when using
        # OSM vector tiles.
        if feature['geometry'].get('coordinates') is None:
            continue

        geom_type = feature['geometry']['type']
        coordinates = feature['geometry']['coordinates']
        if geom_type == 'Polygon':
            polygon_to_label(coordinates[0], crs_transformer)
        else:
            raise Exception(
                'Geometries of type {} are not supported in chip classification \
                labels.'.format(geom_type))
    return labels


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
