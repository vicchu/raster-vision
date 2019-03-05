from abc import ABC, abstractmethod

import shapely

from rastervision.data.vector_source.class_inference import (
    ClassInference, ClassInferenceOptions)


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
        self.geoms = None

    def get_geojson(self):
        if self.geojson is None:
            self.geojson = self._get_geojson()
        return self.geojson

    def get_geoms(self):
        """Convert GeoJSON into list of shapely geoms in pixel-based coords.

        Returns:
            List of (shapely.geometry, class_id) tuples
        """
        if self.geoms is None:
            self.geoms = self._get_geoms(self)
        return self.geoms

    def _get_geoms(self):
        geojson = self.get_geojson()
        features = geojson['features']
        shapes = []

        for feature in features:
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
                geoms = [g.buffer(0) for g in geoms]

            # Convert map to pixel coords.
            def transform_shape(x, y, z=None):
                return self.crs_transformer.map_to_pixel((x, y))

            geoms = [shapely.ops.transform(transform_shape, g) for g in geoms]

            # Tack on class_id.
            class_id = feature['properties']['class_id']
            shapes.extend([(g, class_id) for g in geoms])

        return shapes

    @abstractmethod
    def _get_geojson(self):
        pass
