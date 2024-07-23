"""Helper io utilities for autoRIFT"""

import logging
import sys
import textwrap
from pathlib import Path
from typing import Tuple, Union

from isce.applications.topsApp import TopsInSAR
from osgeo import gdal
from osgeo import ogr
from osgeo import osr

from hyp3_geometry import fix_point_for_antimeridian, flip_point_coordinates

log = logging.getLogger(__name__)


def find_jpl_parameter_info(polygon: ogr.Geometry, parameter_file: str) -> dict:
    driver = ogr.GetDriverByName('ESRI Shapefile')
    shapes = driver.Open(parameter_file, gdal.GA_ReadOnly)

    parameter_info = None
    centroid = flip_point_coordinates(polygon.Centroid())
    centroid = fix_point_for_antimeridian(centroid)
    for feature in shapes.GetLayer(0):
        if feature.geometry().Contains(centroid):
            parameter_info = {
                'name': f'{feature["name"]}',
                'epsg': feature['epsg'],
                'geogrid': {
                    'dem': f"/vsicurl/{feature['h']}",
                    'ssm': f"/vsicurl/{feature['StableSurfa']}",
                    'dhdx': f"/vsicurl/{feature['dhdx']}",
                    'dhdy': f"/vsicurl/{feature['dhdy']}",
                    'vx': f"/vsicurl/{feature['vx0']}",
                    'vy': f"/vsicurl/{feature['vy0']}",
                    'srx': f"/vsicurl/{feature['vxSearchRan']}",
                    'sry': f"/vsicurl/{feature['vySearchRan']}",
                    'csminx': f"/vsicurl/{feature['xMinChipSiz']}",
                    'csminy': f"/vsicurl/{feature['yMinChipSiz']}",
                    'csmaxx': f"/vsicurl/{feature['xMaxChipSiz']}",
                    'csmaxy': f"/vsicurl/{feature['yMaxChipSiz']}",
                    'sp': f"/vsicurl/{feature['sp']}",
                    'dhdxs': f"/vsicurl/{feature['dhdxs']}",
                    'dhdys': f"/vsicurl/{feature['dhdys']}",
                },
                'autorift': {
                    'grid_location': 'window_location.tif',
                    'init_offset': 'window_offset.tif',
                    'search_range': 'window_search_range.tif',
                    'chip_size_min': 'window_chip_size_min.tif',
                    'chip_size_max': 'window_chip_size_max.tif',
                    'offset2vx': 'window_rdr_off2vel_x_vec.tif',
                    'offset2vy': 'window_rdr_off2vel_y_vec.tif',
                    'stable_surface_mask': 'window_stable_surface_mask.tif',
                    'scale_factor': 'window_scale_factor.tif',
                    'mpflag': 0,
                }
            }
            break

    if parameter_info is None:
        raise ValueError('Could not determine appropriate DEM for:\n'
                        f'    centroid: {centroid}'
                        f'    using: {parameter_file}')

    dem_geotransform = gdal.Info(parameter_info['geogrid']['dem'], format='json')['geoTransform']
    parameter_info['xsize'] = abs(dem_geotransform[1])
    parameter_info['ysize'] = abs(dem_geotransform[5])

    return parameter_info


def format_tops_xml(reference, secondary, polarization, dem, orbits, xml_file='topsApp.xml'):
    xml_template = f"""    <?xml version="1.0" encoding="UTF-8"?>
    <topsApp>
        <component name="topsinsar">
            <component name="reference">
                <property name="orbit directory">{orbits}</property>
                <property name="auxiliary data directory">{orbits}</property>
                <property name="output directory">reference</property>
                <property name="safe">['{reference}.zip']</property>
                <property name="polarization">{polarization}</property>
            </component>
            <component name="secondary">
                <property name="orbit directory">{orbits}</property>
                <property name="auxiliary data directory">{orbits}</property>
                <property name="output directory">secondary</property>
                <property name="safe">['{secondary}.zip']</property>
                <property name="polarization">{polarization}</property>
            </component>
            <property name="demfilename">{dem}</property>
            <property name="do interferogram">False</property>
            <property name="do dense offsets">True</property>
            <property name="do ESD">False</property>
            <property name="do unwrap">False</property>
            <property name="do unwrap 2 stage">False</property>
            <property name="ampcor skip width">32</property>
            <property name="ampcor skip height">32</property>
            <property name="ampcor search window width">51</property>
            <property name="ampcor search window height">51</property>
            <property name="ampcor window width">32</property>
            <property name="ampcor window height">32</property>
        </component>
    </topsApp>
    """

    with open(xml_file, 'w') as f:
        f.write(textwrap.dedent(xml_template))


class SysArgvManager:
    """Context manager to clear and reset sys.argv

    A bug in the ISCE2 Application class causes sys.argv to always be parsed when
    no options are proved, even when setting `cmdline=[]`, preventing programmatic use.
    """
    def __init__(self):
        self.argv = sys.argv.copy()

    def __enter__(self):
        sys.argv = sys.argv[:1]

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.argv = self.argv


def get_topsinsar_config():
    with SysArgvManager():
        insar = TopsInSAR(name="topsApp")
        insar.configure()

    config_data = {}
    for name in ['reference', 'secondary']:
        scene = insar.__getattribute__(name)

        sensing_times = []
        for swath in range(1, 4):
            scene.configure()
            scene.swathNumber = swath
            scene.parse()
            sensing_times.append(
                (scene.product.sensingStart, scene.product.sensingStop)
            )

        sensing_start = min([sensing_time[0] for sensing_time in sensing_times])
        sensing_stop = max([sensing_time[1] for sensing_time in sensing_times])

        sensing_dt = (sensing_stop - sensing_start) / 2 + sensing_start

        config_data[f'{name}_filename'] = Path(scene.safe[0]).name
        config_data[f'{name}_dt'] = sensing_dt.strftime("%Y%m%dT%H:%M:%S.%f").rstrip('0')

    return config_data


def load_geospatial(infile: str, band: int = 1):
    ds = gdal.Open(infile, gdal.GA_ReadOnly)

    data = ds.GetRasterBand(band).ReadAsArray()
    nodata = ds.GetRasterBand(band).GetNoDataValue()
    projection = ds.GetProjection()
    transform = ds.GetGeoTransform()
    del ds
    return data, transform, projection, nodata


def write_geospatial(outfile: str, data, transform, projection, nodata,
                     driver: str = 'GTiff', dtype: int = gdal.GDT_Float64) -> str:
    driver = gdal.GetDriverByName(driver)

    rows, cols = data.shape
    ds = driver.Create(outfile, cols, rows, 1, dtype)
    ds.SetGeoTransform(transform)
    ds.SetProjection(projection)

    if nodata is not None:
        ds.GetRasterBand(1).SetNoDataValue(nodata)
    ds.GetRasterBand(1).WriteArray(data)
    del ds
    return outfile


def get_epsg_code(info: dict) -> int:
    """Get the EPSG code from a GDAL Info dictionary
    Args:
        info: The dictionary returned by a gdal.Info call
    Returns:
        epsg_code: The integer EPSG code
    """
    proj = osr.SpatialReference(info['coordinateSystem']['wkt'])
    epsg_code = int(proj.GetAttrValue('AUTHORITY', 1))
    return epsg_code


def ensure_same_projection(reference_path: Union[str, Path], secondary_path: Union[str, Path]) -> Tuple[str, str]:
    reprojection_dir = Path('reprojected')
    reprojection_dir.mkdir(exist_ok=True)

    ref_info = gdal.Info(str(reference_path), format='json')
    ref_epsg = get_epsg_code(ref_info)

    reprojected_reference = str(reprojection_dir / Path(reference_path).name)
    reprojected_secondary = str(reprojection_dir / Path(secondary_path).name)

    gdal.Warp(reprojected_reference, str(reference_path), dstSRS=f'EPSG:{ref_epsg}',
              xRes=ref_info['geoTransform'][1], yRes=ref_info['geoTransform'][5],
              resampleAlg='lanczos', targetAlignedPixels=True)
    gdal.Warp(reprojected_secondary, str(secondary_path), dstSRS=f'EPSG:{ref_epsg}',
              xRes=ref_info['geoTransform'][1], yRes=ref_info['geoTransform'][5],
              resampleAlg='lanczos', targetAlignedPixels=True)

    return reprojected_reference, reprojected_secondary

