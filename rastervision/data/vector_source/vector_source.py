from abc import ABC, abstractmethod

import shapely

from rastervision.data.vector_source.class_inference import (
    ClassInference, ClassInferenceOptions)


def transform_geojson(geojson, crs_transformer=None):
    new_features = []
    for feature in geojson['features']:
        # This was added to handle empty geoms which appear when using
        # OSM vector tiles.
        if feature['geometry'].get('coordinates') is None:
            continue

        geom = shapely.geometry.shape(feature['geometry'])
        geoms = [geom]

        # Convert MultiX to list of X.
        if geom.geom_type in ['MultiPolygon', 'MultiPoint', 'MultiLineString']:
            geoms = list(geom)

        # Use buffer trick to handle self-intersecting polygons.
        if geoms[0].geom_type == 'Polygon':
            buf_geoms = []
            # Note: buffer returns a MultiPolygon if there is a bowtie.
            for g in geoms:
                buf_geoms.extend(list(g.buffer(0)))
            geoms = buf_geoms

        if crs_transformer is not None:
            # Convert map to pixel coords.
            def transform_shape(x, y, z=None):
                return crs_transformer.map_to_pixel((x, y))

            geoms = [shapely.ops.transform(transform_shape, g) for g in geoms]

        for g in geoms:
            new_f = {
                'type': 'Feature',
                'geometry': shapely.mapping(g),
                'properties': feature.get('properties')
            }
            new_features.append(new_f)

    return {'type': 'FeatureCollection', 'features': new_features}


class VectorSource(ABC):
    """A source of vector data.

    Uses GeoJSON as its internal representation of vector data.
    """

    def __init__(self, crs_transformer, class_inf_opts=None):
        """Constructor.

        Args:
            class_inf_opts: (ClassInferenceOptions)
        """
        self.crs_transformer = crs_transformer
        if class_inf_opts is None:
            class_inf_opts = ClassInferenceOptions()
        self.class_inference = ClassInference(class_inf_opts)

        self.geojson = None

    def get_geojson(self, to_pixel=True):
        if self.geojson is None:
            self.geojson = self._get_geojson()
        return transform_geojson(
            self.geojson,
            crs_transformer=(self.crs_transformer if to_pixel else None))

    @abstractmethod
    def _get_geojson(self):
        pass
