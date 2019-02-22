import logging
import math
import os
import pyproj
import subprocess
from decimal import Decimal

from rastervision.core.box import Box
from rastervision.data.crs_transformer import RasterioCRSTransformer
from rastervision.data.raster_source.rasterio_source \
    import RasterioRasterSource
from rastervision.utils.files import download_if_needed, gdalify

log = logging.getLogger(__name__)
wgs84 = pyproj.Proj({'init': 'epsg:4326'})
wgs84_proj4 = '+init=epsg:4326'
meters_per_degree = 111319.5


def build_vrt(image_uris, temp_dir, download=True):
    log.info('Building VRT...')
    if download:
        image_paths = [download_if_needed(uri, temp_dir) for uri in image_uris]
    else:
        image_paths = [gdalify(uri) for uri in image_uris]
    vrt_path = os.path.join(temp_dir, 'index.vrt')

    # https://stackoverflow.com/questions/36287720/boto3-get-credentials-dynamically
    # TODO only do this if using s3 uris
    import boto3
    session = boto3.Session()
    credentials = session.get_credentials()
    credentials = credentials.get_frozen_credentials()
    access_key = credentials.access_key
    secret_key = credentials.secret_key
    aws_env = os.environ.copy()
    aws_env['AWS_SECRET_ACCESS_KEY'] = secret_key
    aws_env['AWS_ACCESS_KEY_ID'] = access_key

    cmd = ['gdalbuildvrt', vrt_path]
    cmd.extend(image_paths)
    print(cmd)
    subprocess.run(cmd, env=aws_env)

    return vrt_path


class GeoTiffSource(RasterioRasterSource):
    def __init__(self,
                 uris,
                 raster_transformers,
                 temp_dir,
                 channel_order=None,
                 x_shift_meters=0.0,
                 y_shift_meters=0.0):
        self.x_shift_meters = x_shift_meters
        self.y_shift_meters = y_shift_meters
        self.uris = uris
        super().__init__(raster_transformers, temp_dir, channel_order)

    def _get_image_path(self, temp_dir, download=True):
        return build_vrt(self.uris, temp_dir, download=download)

    def _set_crs_transformer(self, image_dataset):
        self.crs_transformer = RasterioCRSTransformer.from_dataset(image_dataset)

    def _get_chip(self, window):
        no_shift = self.x_shift_meters == 0.0 and self.y_shift_meters == 0.0
        yes_shift = not no_shift
        if yes_shift:
            ymin, xmin, ymax, xmax = window.tuple_format()
            width = window.get_width()
            height = window.get_height()

            # Transform image coordinates into world coordinates
            transform = self.image_dataset.transform
            xmin2, ymin2 = transform * (xmin, ymin)

            # Transform from world coordinates to WGS84
            if self.crs != wgs84_proj4 and self.proj:
                lon, lat = pyproj.transform(self.proj, wgs84, xmin2, ymin2)
            else:
                lon, lat = xmin2, ymin2

            # Shift.  This is performed by computing the shifts in
            # meters to shifts in degrees.  Those shifts are then
            # applied to the WGS84 coordinate.
            #
            # Courtesy of https://gis.stackexchange.com/questions/2951/algorithm-for-offsetting-a-latitude-longitude-by-some-amount-of-meters  # noqa
            lat_radians = math.pi * lat / 180.0
            dlon = Decimal(self.x_shift_meters) / Decimal(
                meters_per_degree * math.cos(lat_radians))
            dlat = Decimal(self.y_shift_meters) / Decimal(meters_per_degree)
            lon = float(Decimal(lon) + dlon)
            lat = float(Decimal(lat) + dlat)

            # Transform from WGS84 to world coordinates
            if self.crs != wgs84_proj4 and self.proj:
                xmin3, ymin3 = pyproj.transform(wgs84, self.proj, lon, lat)
                xmin3 = int(round(xmin3))
                ymin3 = int(round(ymin3))
            else:
                xmin3, ymin3 = lon, lat

            # Trasnform from world coordinates back into image coordinates
            xmin4, ymin4 = ~transform * (xmin3, ymin3)

            window = Box(ymin4, xmin4, ymin4 + height, xmin4 + width)

        return super()._get_chip(window)

    def _activate(self):
        super()._activate()
        self.crs = self.image_dataset.crs
        if self.crs:
            self.proj = pyproj.Proj(self.crs)
        else:
            self.proj = None
        self.crs = str(self.crs)
