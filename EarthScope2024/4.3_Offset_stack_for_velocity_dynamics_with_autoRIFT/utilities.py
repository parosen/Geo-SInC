
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
import datetime
from osgeo import gdal, osr, ogr
import glob
import os

def write_gdal(filename, array, geoTransform, epsg=3031, dtype=gdal.GDT_Float32):
    """
    Helper function to write an array to a raster.
    """
    # Make a list of arrays
    if not isinstance(array, (list, tuple)):
        array = [array,]
    Ny, Nx = array[0].shape
    N_bands = len(array)

    # Initialize dataset with geographic info
    driver = gdal.GetDriverByName('GTiff')
    ds = driver.Create(filename, xsize=Nx, ysize=Ny, bands=N_bands, eType=dtype)
    ds.SetGeoTransform(geoTransform)
    srs = osr.SpatialReference()
    srs.SetFromUserInput('EPSG:%d' % epsg)
    ds.SetProjection(srs.ExportToWkt())

    # Write raster data
    for bnum in range(N_bands):
        b = ds.GetRasterBand(bnum + 1)
        b.WriteArray(array[bnum])
        
    ds = None

def create_hillshade(filename, vert_exag=1.2, dx=None, dy=None, azdeg=315, altdeg=45):
    """
    Load DEM raster and create a hillshade array.
    """
    # Load DEM data
    ds = gdal.Open(filename, gdal.GA_ReadOnly)
    z = ds.GetRasterBand(1).ReadAsArray()
    extent = extent_from_ds(ds)
    if dx is None or dy is None:
        _, dx, _, _, _, dy = ds.GetGeoTransform()
    ds = None 

    ls = LightSource(azdeg=azdeg, altdeg=altdeg)
    hs = ls.hillshade(z, vert_exag=vert_exag, dx=dx, dy=dy)

    return hs, extent

def extent_from_ds(ds):
    """
    Unpack geotransform of GDAL dataset in order to compute map extents.
    """
    # Get raster size
    Ny = ds.RasterYSize
    Nx = ds.RasterXSize
    
    # Unpack geotransform
    try:
        xstart, dx, _, ystart, _, dy = ds.GetGeoTransform()
    except AttributeError:
        ystart = xstart = 0.0
        dx = dy = 1.0
        
    # Compute and return extent
    xstop = xstart + (Nx - 1) * dx
    ystop = ystart + (Ny - 1) * dy
    return np.array([xstart, xstop, ystop, ystart])

def plot_offsets(results_dir='merged', xlim=None, ylim=None, snr_thresh=5.0, r_clim=(-6, 6), az_clim=(-6, 6)):
    """
    Plot geocoded offsets on top of DEM. The offsets are scaled
    to meters/year units.
    """
    # Load hillshade for DEM
    hs, hs_extent = create_hillshade('cropped_nasadem_wgs84.tif', dx=30, dy=30)

    # Load offsets
    fname = os.path.join(results_dir, 'filt_dense_offsets.bil.geo')
    ds = gdal.Open(fname, gdal.GA_ReadOnly)
    a_vel = ds.GetRasterBand(1).ReadAsArray()
    r_vel = ds.GetRasterBand(2).ReadAsArray()
    offset_extent = extent_from_ds(ds)
    ds = None

    # Load SNR
    fname = os.path.join(results_dir, 'dense_offsets_snr.bil.geo')
    ds = gdal.Open(fname, gdal.GA_ReadOnly)
    snr = ds.GetRasterBand(1).ReadAsArray()
    ds = None

    # Mask zeros and low SNR values
    mask = (np.abs(a_vel) < 1.0e-5) + (snr < snr_thresh)
    a_vel[mask] = np.nan
    r_vel[mask] = np.nan
    
    # Initialize figure
    fig, (ax1, ax2) = plt.subplots(nrows=2, figsize=(12, 11))

    def imshow(ax, arr, extent=None, cmap='RdBu_r', clim=(-5, 5), cbar=True, **kwargs):
        im = ax.imshow(arr, cmap=cmap, clim=clim, extent=extent, **kwargs)
        if cbar:
            cb = plt.colorbar(im, ax=ax, pad=0.02)
            return im, cb
        else:
            return im

    # Plot DEM as background
    imshow(ax1, hs, extent=hs_extent, cmap='gray', cbar=False, clim=(0, 0.9))
    imshow(ax2, hs, extent=hs_extent, cmap='gray', cbar=False, clim=(0, 0.9))

    # Plot offsets
    imshow(ax1, r_vel, extent=offset_extent, clim=r_clim, alpha=0.7, aspect='auto')
    imshow(ax2, a_vel, extent=offset_extent, clim=az_clim, alpha=0.7, aspect='auto')

    # Decoration
    ax1.set_title('Pixel offsets in range direction')
    ax2.set_title('Pixel offsets in azimuth direction')
    for ax in (ax1, ax2):
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
    fig.set_tight_layout(True)

def plot_autorift_offsets(filename='velocity.tif', vx_clim=(-8, 8), vy_clim=(-8, 8),
                          xtitle='Velocity in X-direction (m/yr)', ytitle='Velocity in Y-direction (m/yr)'):
    """
    Plot geocoded autoRIFT offsets on top of LIMA background. The offsets are scaled
    to meters/year units.
    """
    # Load hillshade for DEM
    hs, hs_extent = create_hillshade('cropped_nasadem_utm.tif')

    # Load offsets
    ds = gdal.Open(filename, gdal.GA_ReadOnly)
    y_vel = ds.GetRasterBand(2).ReadAsArray()
    x_vel = ds.GetRasterBand(1).ReadAsArray()
    offset_extent = extent_from_ds(ds)
    ds = None

    # Initialize figure
    fig, (ax1, ax2) = plt.subplots(nrows=2, figsize=(8, 11))

    def imshow(ax, arr, extent=None, cmap='RdBu_r', clim=(-5, 5), cbar=True, **kwargs):
        im = ax.imshow(arr, cmap=cmap, clim=clim, extent=extent, **kwargs)
        if cbar:
            cb = plt.colorbar(im, ax=ax, pad=0.02)
            return im, cb
        else:
            return im

    # Plot DEM as background
    imshow(ax1, hs, extent=hs_extent, cmap='gray', cbar=False, clim=(0, 1))
    imshow(ax2, hs, extent=hs_extent, cmap='gray', cbar=False, clim=(0, 1))

    # Plot offsets
    imshow(ax1, x_vel, extent=offset_extent, clim=vx_clim, alpha=0.7, aspect='auto')
    imshow(ax2, y_vel, extent=offset_extent, clim=vy_clim, alpha=0.7, aspect='auto')

    # Decoration
    ax1.set_title(xtitle)
    ax2.set_title(ytitle)
    for ax in (ax1, ax2):
        ax.set_xlabel('Easting')
        ax.set_ylabel('Northing')
    fig.set_tight_layout(True)

# end of file
