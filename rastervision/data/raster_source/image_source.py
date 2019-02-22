from rastervision.data.raster_source.rasterio_source import (
    RasterioRasterSource)
from rastervision.data.crs_transformer.identity_crs_transformer import (
    IdentityCRSTransformer)
from rastervision.utils.files import download_if_needed, gdalify


class ImageSource(RasterioRasterSource):
    def __init__(self, uri, raster_transformers, temp_dir, channel_order=None):
        self.uri = uri
        super().__init__(raster_transformers, temp_dir, channel_order)

    def _get_image_path(self, temp_dir, download=False):
        if download:
            return download_if_needed(self.uri, self.temp_dir)
        else:
            return gdalify(self.uri)

    def _set_crs_transformer(self, image_dataset):
        self.crs_transformer = IdentityCRSTransformer()
