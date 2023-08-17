
import numpy as np
import matplotlib.pyplot as plt
import datetime
from osgeo import gdal, osr, ogr
import glob
import os

def write_gdal(filename, array, geoTransform, epsg=3031, dtype=gdal.GDT_Float32):
    """
    Helper function to write an array to a raster.
    """
    # Get array shape
    Ny, Nx = array.shape

    # Initialize dataset with geographic info
    driver = gdal.GetDriverByName('GTiff')
    ds = driver.Create(filename, xsize=Nx, ysize=Ny, bands=1, eType=dtype)
    ds.SetGeoTransform(geoTransform)
    srs = osr.SpatialReference()
    srs.SetFromUserInput('EPSG:%d' % epsg)
    ds.SetProjection(srs.ExportToWkt())

    # Write raster data
    b = ds.GetRasterBand(1)
    b.WriteArray(array)
    ds = None

def load_lima(parent_dir):
    """
    Load the LIMA background image and tweak the RGB bands for better visualization.
    """
    # Load bands
    path = os.path.join(parent_dir, 'support_files', 'pig_lima_rgb_wgs84.dat')
    ds = gdal.Open(path, gdal.GA_ReadOnly)
    b = ds.GetRasterBand(1).ReadAsArray()
    g = ds.GetRasterBand(2).ReadAsArray()
    r = ds.GetRasterBand(3).ReadAsArray()
    
    # Unpack map extent
    extent = extent_from_ds(ds)
    ds = None
    
    # Tweak bands and pack into RGB array
    red = normalize(r, 140, 250)
    green = normalize(g, 100, 230)
    blue = normalize(b, 100, 230)
    alpha = 0.8 * np.ones_like(red)
    rgb = np.dstack((red, green, blue, alpha))

    return rgb, extent

def normalize(x, xmin, xmax):
    """
    Normalize array to [0, 1] values.
    """
    xn =  (x - xmin) / (xmax - xmin)
    return np.clip(xn, 0.0, 1.0)

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

def load_offset_velocity_from_ds(ds, band=1, rangePixel=2.33, azPixel=14.2, dt=6.0):
    
    # Read data into array
    off = ds.GetRasterBand(band).ReadAsArray()
    
    # Scale by pixel size and time separation in order to get velocity
    pixel_sizes = [14.2, 2.33] # [az_pixel, rg_pixel] in meters
    off_meters = off * pixel_sizes[band-1]
    off_vel = off_meters / dt
    
    return off_vel

def plot_offsets(rdir, parent_dir):
    """
    Plot geocoded offsets on top of LIMA background. The offsets are scaled
    to meters/year units.
    """
    # Load background LIMA image
    lima, lima_extent = load_lima(parent_dir)

    # Load offsets
    fname = glob.glob(os.path.join(rdir, 'geo_filt*.bil'))[0]
    ds = gdal.Open(fname, gdal.GA_ReadOnly)
    a_vel = load_offset_velocity_from_ds(ds, band=1)
    r_vel = load_offset_velocity_from_ds(ds, band=2)
    offset_extent = extent_from_ds(ds)
    ds = None

    # Mask zeros
    mask = np.abs(a_vel) < 1.0e-5
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

    # Plot LIMA as background
    imshow(ax1, lima, extent=lima_extent, cmap=None, cbar=False, clim=None)
    imshow(ax2, lima, extent=lima_extent, cmap=None, cbar=False, clim=None)

    # Plot offsets
    imshow(ax1, r_vel, extent=offset_extent, clim=(-1.7, 1.7), alpha=0.7, aspect='auto')
    imshow(ax2, a_vel, extent=offset_extent, clim=(-12.5, 12.5), alpha=0.7, aspect='auto')

    # Decoration
    ax1.set_title('Rate-of-change in range direction (m/day)')
    ax2.set_title('Rate-of-change in azimuth direction (m/day)')
    for ax in (ax1, ax2):
        ax.set_xlim(-104, -96)
        ax.set_ylim(-75.6, -74.4)
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
    fig.set_tight_layout(True)

def plot_autorift_offsets(parent_dir, filename='offset_wgs84.tif',
                          rangePixel=2.33, azPixel=14.2, dt=6.0):
    """
    Plot geocoded autoRIFT offsets on top of LIMA background. The offsets are scaled
    to meters/year units.
    """
    # Load background LIMA image
    lima, lima_extent = load_lima(parent_dir)

    # Load offsets
    ds = gdal.Open(os.path.join(parent_dir, filename), gdal.GA_ReadOnly)
    a_vel = ds.GetRasterBand(2).ReadAsArray() * azPixel / dt
    r_vel = ds.GetRasterBand(1).ReadAsArray() * rangePixel / dt
    offset_extent = extent_from_ds(ds)
    ds = None

    # Initialize figure
    fig, (ax1, ax2) = plt.subplots(nrows=2, figsize=(12, 11))

    def imshow(ax, arr, extent=None, cmap='RdBu_r', clim=(-5, 5), cbar=True, **kwargs):
        im = ax.imshow(arr, cmap=cmap, clim=clim, extent=extent, **kwargs)
        if cbar:
            cb = plt.colorbar(im, ax=ax, pad=0.02)
            return im, cb
        else:
            return im

    # Plot LIMA as background
    imshow(ax1, lima, extent=lima_extent, cmap=None, cbar=False, clim=None)
    imshow(ax2, lima, extent=lima_extent, cmap=None, cbar=False, clim=None)

    # Plot offsets
    imshow(ax1, r_vel, extent=offset_extent, clim=(-1.7, 1.7), alpha=0.7, aspect='auto')
    imshow(ax2, a_vel, extent=offset_extent, clim=(-12.5, 12.5), alpha=0.7, aspect='auto')

    # Decoration
    ax1.set_title('Rate-of-change in range direction (m/day)')
    ax2.set_title('Rate-of-change in azimuth direction (m/day)')
    for ax in (ax1, ax2):
        ax.set_xlim(-104, -96)
        ax.set_ylim(-75.6, -74.4)
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
    fig.set_tight_layout(True)

# end of file
