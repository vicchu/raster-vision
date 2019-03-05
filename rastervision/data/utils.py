import shapely


def geojson_to_shapes(geojson, crs_transformer):
    """Convert GeoJSON into list of shapely geoms in pixel-based coords.

    Args:
        geojson: dict in GeoJSON format with class_id property for each
            feature
        crs_transformer: CRSTransformer used to convert from map to pixel
            coords

    Returns:
        List of (shapely.geometry, class_id) tuples
    """
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
            return crs_transformer.map_to_pixel((x, y))

        geoms = [shapely.ops.transform(transform_shape, g) for g in geoms]

        # Tack on class_id.
        class_id = feature['properties']['class_id']
        shapes.extend([(g, class_id) for g in geoms])

    return shapes


def boxes_to_geojson(boxes, class_ids, crs_transformer, class_map,
                     scores=None):
    """Convert boxes and associated data into a GeoJSON dict.

    Args:
        boxes: list of Box in pixel row/col format.
        class_ids: list of int (one for each box)
        crs_transformer: CRSTransformer used to convert pixel coords to map
            coords in the GeoJSON
        class_map: ClassMap used to infer class_name from class_id
        scores: optional list of score or scores.
                If floats (one for each box), property name will be "score".
                If lists of floats, property name will be "scores".

    Returns:
        dict in GeoJSON format
    """
    features = []
    for box_ind, box in enumerate(boxes):
        polygon = box.geojson_coordinates()
        polygon = [list(crs_transformer.pixel_to_map(p)) for p in polygon]

        class_id = int(class_ids[box_ind])
        class_name = class_map.get_by_id(class_id).name

        feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'Polygon',
                'coordinates': [polygon]
            },
            'properties': {
                'class_id': class_id,
                'class_name': class_name
            }
        }

        if scores is not None:
            box_scores = scores[box_ind]

            if box_scores is not None:
                if type(box_scores) is list:
                    feature['properties']['scores'] = box_scores
                else:
                    feature['properties']['score'] = box_scores

        features.append(feature)

    return {'type': 'FeatureCollection', 'features': features}
