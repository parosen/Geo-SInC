
import numpy as np
import matplotlib.pyplot as plt
import datetime
from osgeo import gdal
import os


def load_power_image(path):
    
    # Load GDAL band
    ds = gdal.Open(path, gdal.GA_ReadOnly)
    img = ds.GetRasterBand(1).ReadAsArray()
    ds = None

    # Convert to dB
    db_ref = 46.9897 # approximate max dB value
    img_db = 10.0 * np.log10(img)
    img_db -= db_ref
    
    return img_db

def load_lima(parent_dir):
    """
    Load the LIMA background image and tweak the RGB bands.
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

def plot_offsets(rdir, parent_dir, snr_thresh=6.0):
    """
    Plot offsets on top of LIMA background. Use SNR raster to mask out offset values with
    SNR < snr_thresh.
    """
    # Load background LIMA image
    lima, lima_extent = load_lima(parent_dir)

    # Load offsets
    ds = gdal.Open(os.path.join(rdir, 'filt_dense_offsets.bil.geo'), gdal.GA_ReadOnly)
    a_vel = load_offset_velocity_from_ds(ds, band=1)
    r_vel = load_offset_velocity_from_ds(ds, band=2)
    offset_extent = extent_from_ds(ds)
    ds = None

    # Load and mask by SNR
    ds = gdal.Open(os.path.join(rdir, 'dense_offsets_snr.bil.geo'), gdal.GA_ReadOnly)
    snr = ds.GetRasterBand(1).ReadAsArray()
    ds = None
    mask = snr < snr_thresh
    r_vel[mask] = np.nan
    a_vel[mask] = np.nan

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


def create_stack(offset_band=1, snr_thresh=6.0):
    
    # Find all offset files
    files = []
    snr_files = []
    tdec = []
    for root, dirs, names in os.walk(os.getcwd()):
        for name in names:
            
            # Store path
            if name != 'filt_dense_offsets.bil.geo':
                continue
            files.append(os.path.join(root, name))
            snr_files.append(os.path.join(root, 'dense_offsets_snr.bil.geo'))
            
            # Get mid-date
            datestr = root.split('/')[-2]
            datestr1, datestr2 = datestr.split('_')
            date1 = datetime.datetime.strptime(datestr1, '%Y%m%d')
            date2 = datetime.datetime.strptime(datestr2, '%Y%m%d')
            dt = date1 - date2
            date_mid = date2 + 0.5 * dt
            
            # Convert mid-date to decimal year
            date_year_start = datetime.datetime(date_mid.year, 1, 1)
            dt = date_mid - date_year_start
            tdec.append(date_mid.year + (dt.total_seconds() / 86400) / 365.0)
            
    # Sort by year
    indsort = np.argsort(tdec)
    files = [files[ind] for ind in indsort]
    snr_files = [snr_files[ind] for ind in indsort]
    tdec = np.array([tdec[ind] for ind in indsort])
    
    # For each file, we sample to a common projWin
    projWin = [-104.0, -74.4, -96.0, -75.6]
    opts = gdal.TranslateOptions(projWin=projWin)
    for cnt, (fname, snr_fname) in enumerate(zip(files, snr_files)):
                
        # Open raster and translate to common projWin
        ds = gdal.Open(fname, gdal.GA_ReadOnly)
        mem_ds = gdal.Translate('/vsimem/temp.tif', ds, options=opts)
        velocity = load_offset_velocity_from_ds(mem_ds, band=offset_band)
        extent = extent_from_ds(mem_ds)
        gdal.Unlink('/vsimem/temp.tif')
        ds = None
        
        # Also load SNR and mask out
        ds = gdal.Open(snr_fname, gdal.GA_ReadOnly)
        mem_ds = gdal.Translate('/vsimem/temp.tif', ds, options=opts)
        snr = mem_ds.GetRasterBand(1).ReadAsArray()
        gdal.Unlink('/vsimem/temp.tif')
        ds = None
        
        # Mask out low SNR
        mask = snr < snr_thresh
        velocity[mask] = np.nan
        
        if cnt == 0:
            stack = velocity
            
        else:
            stack = np.dstack((stack, velocity))
            
    return stack, tdec, extent
