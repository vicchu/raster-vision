from abc import abstractmethod
import tempfile

import numpy as np
import rasterio
from rasterio.enums import (ColorInterp, MaskFlags)

from rastervision.data import (ActivateMixin, ActivationError)
from rastervision.data.raster_source import RasterSource
from rastervision.core.box import Box


def load_window(image_dataset, window=None, channels=None, is_masked=False,
                boundless=True):
    """Load a window of an image from a TIFF file.

    Args:
        window: ((row_start, row_stop), (col_start, col_stop)) or
        ((y_min, y_max), (x_min, x_max))
        channels: An optional list of bands to read.
        is_masked: If True, read a  masked array from rasterio
    """
    if is_masked:
        im = image_dataset.read(window=window, boundless=boundless, masked=True)
        im = np.ma.filled(im, fill_value=0)
    else:
        im = image_dataset.read(window=window, boundless=boundless)

    # Handle non-zero NODATA values by setting the data to 0.
    for channel, nodata in enumerate(image_dataset.nodatavals):
        if nodata is not None and nodata != 0:
            im[channel, im[channel] == nodata] = 0

    if channels:
        im = im[channels, :]
    im = np.transpose(im, axes=[1, 2, 0])
    return im


class RasterioRasterSource(ActivateMixin, RasterSource):
    def __init__(self, raster_transformers, temp_dir, channel_order=None):
        self.temp_dir = temp_dir
        self.image_temp_dir = None
        self.image_dataset = None
        num_channels = None

        # Get some metadata from the imagery without downloading it.
        image_path = self._get_image_path(self.temp_dir, download=False)
        print('before open')
        with rasterio.open(image_path) as image_dataset:
            print('after open')
            colorinterp = image_dataset.colorinterp
            self.channels = [
                i for i, color_interp in enumerate(colorinterp)
                if color_interp != ColorInterp.alpha
            ]

            mask_flags = image_dataset.mask_flag_enums
            self.is_masked = any(
                [m for m in mask_flags if m != MaskFlags.all_valid])

            self.height = image_dataset.height
            self.width = image_dataset.width
            # Get 1x1 chip (after applying raster transformers) to test dtype
            # and channel order if needed
            test_chip = load_window(
                image_dataset, Box.make_square(0, 0, 1).rasterio_format(), self.channels,
                boundless=False)

            raw_channels = list(range(0, test_chip.shape[2]))
            self.channel_order = channel_order or raw_channels
            num_channels = len(raw_channels)

            # Transform the chip to get the final dtype
            test_chip = test_chip[:, :, self.channel_order]
            for transformer in raster_transformers:
                test_chip = transformer.transform(test_chip, channel_order)

            self.dtype = test_chip.dtype
            print('before getting crs')
            self._set_crs_transformer(image_dataset)
            print('after getting crs')

        super().__init__(channel_order, num_channels, raster_transformers)

    @abstractmethod
    def _get_image_path(self, tmp_dir, download=True):
        """Download any data needed for this Raster Source.
        Return a single local path representing the image or a VRT of the data."""
        pass

    @abstractmethod
    def _set_crs_transformer(self, image_dataset):
        pass

    def get_crs_transformer(self):
        return self.crs_transformer

    def get_extent(self):
        return Box(0, 0, self.height, self.width)

    def get_dtype(self):
        """Return the numpy.dtype of this scene"""
        return self.dtype

    def _get_chip(self, window):
        if self.image_dataset is None:
            raise ActivationError('RasterSource must be activated before use')
        return load_window(self.image_dataset, window.rasterio_format(),
                           self.channels)

    def _activate(self):
        # Download images to temporary directory and delete it when done.
        self.image_temp_dir = tempfile.TemporaryDirectory(dir=self.temp_dir)
        self.imagery_path = self._get_image_path(self.image_temp_dir.name, download=True)
        self.image_dataset = rasterio.open(self.imagery_path)

    def _deactivate(self):
        self.image_dataset.close()
        self.image_dataset = None
        self.image_temp_dir.cleanup()
        self.image_temp_dir = None
