#!/usr/bin/env python3

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Copyright 2019 California Institute of Technology. ALL RIGHTS RESERVED.
# Modifications Copyright 2021 Alaska Satellite Facility
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# United States Government Sponsorship acknowledged. This software is subject to
# U.S. export control laws and regulations and has been classified as 'EAR99 NLR'
# (No [Export] License Required except when exporting to an embargoed country,
# end user, or in support of a prohibited end use). By downloading this software,
# the user agrees to comply with all applicable U.S. export laws and regulations.
# The user has the responsibility to obtain export licenses, or other export
# authority as may be required before exporting this software to any 'EAR99'
# embargoed foreign country or citizen of those countries.
#
# Authors: Piyush Agram, Yang Lei
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
from typing import Tuple
from pathlib import Path


def cmdLineParse():
    '''
    Command line parser.
    '''
    import argparse

    parser = argparse.ArgumentParser(description='Output geo grid')
    parser.add_argument('-m', '--input_m', dest='indir_m', type=str, required=True,
            help='Input folder with ISCE swath files for master image or master image file name (in GeoTIFF format and Cartesian coordinates)')
    parser.add_argument('-s', '--input_s', dest='indir_s', type=str, required=True,
            help='Input folder with ISCE swath files for slave image or slave image file name (in GeoTIFF format and Cartesian coordinates)')
#    parser.add_argument('-o', '--output', dest='outfile', type=str, default='geogrid.csv',
#            help='Output grid mapping')
    parser.add_argument('-d', '--dem', dest='demfile', type=str, required=True,
            help='Input DEM')
    parser.add_argument('-sx', '--dhdx', dest='dhdxfile', type=str, default="",
            help='Input slope in X')
    parser.add_argument('-sy', '--dhdy', dest='dhdyfile', type=str, default="",
            help='Input slope in Y')
    parser.add_argument('-vx', '--vx', dest='vxfile', type=str, default="",
            help='Input velocity in X')
    parser.add_argument('-vy', '--vy', dest='vyfile', type=str, default="",
            help='Input velocity in Y')
    parser.add_argument('-srx', '--srx', dest='srxfile', type=str, default="",
            help='Input search range in X')
    parser.add_argument('-sry', '--sry', dest='sryfile', type=str, default="",
            help='Input search range in Y')
    parser.add_argument('-csminx', '--csminx', dest='csminxfile', type=str, default="",
            help='Input chip size min in X')
    parser.add_argument('-csminy', '--csminy', dest='csminyfile', type=str, default="",
            help='Input chip size min in Y')
    parser.add_argument('-csmaxx', '--csmaxx', dest='csmaxxfile', type=str, default="",
            help='Input chip size max in X')
    parser.add_argument('-csmaxy', '--csmaxy', dest='csmaxyfile', type=str, default="",
            help='Input chip size max in Y')
    parser.add_argument('-ssm', '--ssm', dest='ssmfile', type=str, default="",
            help='Input stable surface mask')
    parser.add_argument('-fo', '--flag_optical', dest='optical_flag', type=bool, required=False, default=0,
            help='flag for reading optical data (e.g. Landsat): use 1 for on and 0 (default) for off')
    parser.add_argument('-b', '--buffer', dest='buffer', type=bool, required=False, default=0,
            help='buffer to add to the starting/end range accounting for all passes from the same relative orbit')
    parser.add_argument('-p', '--parse', dest='parse', action='store_true',
            default=False, help='Parse the SAFE zip file to get radar image and orbit metadata; no need to run ISCE')

    return parser.parse_args()

class Dummy(object):
    pass


def loadProduct(xmlname):
    '''
    Load the product using Product Manager.
    '''
    import isce
    from iscesys.Component.ProductManager import ProductManager as PM

    pm = PM()
    pm.configure()

    obj = pm.loadProduct(xmlname)

    return obj


def getMergedOrbit(product):
    import isce
    from isceobj.Orbit.Orbit import Orbit

    ###Create merged orbit
    orb = Orbit()
    orb.configure()

    burst = product[0].bursts[0]
    #Add first burst orbit to begin with
    for sv in burst.orbit:
        orb.addStateVector(sv)


    for pp in product:
        ##Add all state vectors
        for bb in pp.bursts:
            for sv in bb.orbit:
                if (sv.time< orb.minTime) or (sv.time > orb.maxTime):
                    orb.addStateVector(sv)

    return orb


def loadMetadata(indir,buffer=0):
    '''
    Input file.
    '''
    import os
    import numpy as np

    frames = []
    for swath in range(1,4):
        inxml = os.path.join(indir, 'IW{0}.xml'.format(swath))
        if os.path.exists(inxml):
            ifg = loadProduct(inxml)
            frames.append(ifg)

    info = Dummy()
    info.sensingStart = min([x.sensingStart for x in frames])
    info.sensingStop = max([x.sensingStop for x in frames])
    info.startingRange = min([x.startingRange for x in frames])
    info.farRange = max([x.farRange for x in frames])
    info.prf = 1.0 / frames[0].bursts[0].azimuthTimeInterval
    info.rangePixelSize = frames[0].bursts[0].rangePixelSize
    info.lookSide = -1
        
    info.startingRange -= buffer * info.rangePixelSize
    info.farRange += buffer * info.rangePixelSize
    
    info.numberOfLines = int( np.round( (info.sensingStop - info.sensingStart).total_seconds() * info.prf)) + 1
    info.numberOfSamples = int( np.round( (info.farRange - info.startingRange)/info.rangePixelSize)) + 1  + 2 * buffer
    info.orbit = getMergedOrbit(frames)

    return info


def get_polarizations(s1_safe: str) -> Tuple[str]:
    mapping = {
        'SH': ('hh',),
        'SV': ('vv',),
        'DH': ('hh', 'hv'),
        'DV': ('vv', 'vh'),
    }
    key = Path(s1_safe).name[14:16]
    return mapping[key]


def loadParsedata(indir, orbit_dir, aux_dir, buffer=0):
    '''
    Input file.
    '''
    import os
    import numpy as np
    import isce
    from isceobj.Sensor.TOPS.Sentinel1 import Sentinel1
    

    frames = []
    for swath in range(1,4):
        rdr=Sentinel1()
        rdr.configure()
#        rdr.safe=['./S1A_IW_SLC__1SDH_20180401T100057_20180401T100124_021272_024972_8CAF.zip']
        rdr.safe=[indir]
        rdr.output='reference'
        rdr.orbitDir=orbit_dir
        rdr.auxDir=aux_dir
        rdr.swathNumber=swath
        rdr.polarization=get_polarizations(indir)[0]
        rdr.parse()
        frames.append(rdr.product)
    
    info = Dummy()
    info.sensingStart = min([x.sensingStart for x in frames])
    info.sensingStop = max([x.sensingStop for x in frames])
    info.startingRange = min([x.startingRange for x in frames])
    info.farRange = max([x.farRange for x in frames])
    info.prf = 1.0 / frames[0].bursts[0].azimuthTimeInterval
    info.rangePixelSize = frames[0].bursts[0].rangePixelSize
    info.lookSide = -1
    
    info.startingRange -= buffer * info.rangePixelSize
    info.farRange += buffer * info.rangePixelSize
    
    info.numberOfLines = int( np.round( (info.sensingStop - info.sensingStart).total_seconds() * info.prf)) + 1
    info.numberOfSamples = int( np.round( (info.farRange - info.startingRange)/info.rangePixelSize)) + 1 + 2 * buffer
    info.orbit = getMergedOrbit(frames)
    
    return info

def coregisterLoadMetadataOptical(indir_m, indir_s, **kwargs):
    '''
    Input file.
    '''
    import os
    import numpy as np

    from osgeo import gdal, osr
    import struct
    import re

    import isce
    from components.contrib.geo_autoRIFT.geogrid import GeogridOptical
#    from geogrid import GeogridOptical

    obj = GeogridOptical()

    x1a, y1a, xsize1, ysize1, x2a, y2a, xsize2, ysize2, trans = obj.coregister(indir_m, indir_s)

    DS = gdal.Open(indir_m, gdal.GA_ReadOnly)

    info = Dummy()
    info.startingX = trans[0]
    info.startingY = trans[3]
    info.XSize = trans[1]
    info.YSize = trans[5]

    if re.findall("L[CO]0[89]_",DS.GetDescription()).__len__() > 0:
        nameString = os.path.basename(DS.GetDescription())
        info.time = nameString.split('_')[3]
    elif re.findall("L[EO]07_",DS.GetDescription()).__len__() > 0:
        nameString = os.path.basename(DS.GetDescription())
        info.time = nameString.split('_')[3]
    elif re.findall("LT0[45]_",DS.GetDescription()).__len__() > 0:
        nameString = os.path.basename(DS.GetDescription())
        info.time = nameString.split('_')[3]
    elif 'sentinel-s2-l1c' in indir_m or 's2-l1c-us-west-2' in indir_m:
        s2_name = kwargs['reference_metadata']['id']
        info.time = s2_name.split('_')[2]
    elif re.findall("S2._",DS.GetDescription()).__len__() > 0:
        info.time = DS.GetDescription().split('_')[2]
    else:
        raise Exception('Optical data NOT supported yet!')

    info.numberOfLines = ysize1
    info.numberOfSamples = xsize1

    info.filename = indir_m

    DS1 = gdal.Open(indir_s, gdal.GA_ReadOnly)

    info1 = Dummy()

    if re.findall("L[CO]0[89]_",DS1.GetDescription()).__len__() > 0:
        nameString1 = os.path.basename(DS1.GetDescription())
        info1.time = nameString1.split('_')[3]
    elif re.findall("L[EO]07_",DS1.GetDescription()).__len__() > 0:
        nameString1 = os.path.basename(DS1.GetDescription())
        info1.time = nameString1.split('_')[3]
    elif re.findall("LT0[45]_",DS1.GetDescription()).__len__() > 0:
        nameString1 = os.path.basename(DS1.GetDescription())
        info1.time = nameString1.split('_')[3]
    elif 'sentinel-s2-l1c' in indir_s or 's2-l1c-us-west-2' in indir_s:
        s2_name = kwargs['secondary_metadata']['id']
        info1.time = s2_name.split('_')[2]
    elif re.findall("S2._",DS1.GetDescription()).__len__() > 0:
        info1.time = DS1.GetDescription().split('_')[2]
    else:
        raise Exception('Optical data NOT supported yet!')

    return info, info1


def runGeogrid(info, info1, dem, dhdx, dhdy, vx, vy, srx, sry, csminx, csminy, csmaxx, csmaxy, ssm, **kwargs):
    '''
    Wire and run geogrid.
    '''

    import isce
    from components.contrib.geo_autoRIFT.geogrid import Geogrid
#    from geogrid import Geogrid

    from osgeo import gdal
    dem_info = gdal.Info(dem, format='json')

    obj = Geogrid()
    obj.configure()

    obj.startingRange = info.startingRange
    obj.rangePixelSize = info.rangePixelSize
    obj.sensingStart = info.sensingStart
    obj.prf = info.prf
    obj.lookSide = info.lookSide
    obj.repeatTime = (info1.sensingStart - info.sensingStart).total_seconds()
    obj.numberOfLines = info.numberOfLines
    obj.numberOfSamples = info.numberOfSamples
    obj.nodata_out = -32767
    obj.chipSizeX0 = 240
    obj.gridSpacingX = dem_info['geoTransform'][1]
    obj.orbit = info.orbit
    obj.demname = dem
    obj.dhdxname = dhdx
    obj.dhdyname = dhdy
    obj.vxname = vx
    obj.vyname = vy
    obj.srxname = srx
    obj.sryname = sry
    obj.csminxname = csminx
    obj.csminyname = csminy
    obj.csmaxxname = csmaxx
    obj.csmaxyname = csmaxy
    obj.ssmname = ssm
    obj.winlocname = "window_location.tif"
    obj.winoffname = "window_offset.tif"
    obj.winsrname = "window_search_range.tif"
    obj.wincsminname = "window_chip_size_min.tif"
    obj.wincsmaxname = "window_chip_size_max.tif"
    obj.winssmname = "window_stable_surface_mask.tif"
    obj.winro2vxname = "window_rdr_off2vel_x_vec.tif"
    obj.winro2vyname = "window_rdr_off2vel_y_vec.tif"
    obj.winsfname = "window_scale_factor.tif"
    ##dt-varying search range scale (srs) rountine parameters
#    obj.srs_dt_unity = 5
#    obj.srs_max_scale = 10
#    obj.srs_max_search = 20000
#    obj.srs_min_search = 0

    obj.getIncidenceAngle()
    obj.geogrid()

    run_info = {
        'chipsizex0': obj.chipSizeX0,
        'gridspacingx': obj.gridSpacingX,
        'vxname': vx,
        'vyname': vy,
        'sxname': kwargs.get('dhdxs'),
        'syname': kwargs.get('dhdys'),
        'maskname': kwargs.get('sp'),
        'xoff': obj.pOff,
        'yoff': obj.lOff,
        'xcount': obj.pCount,
        'ycount': obj.lCount,
        'dt': obj.repeatTime,
        'epsg': kwargs.get('epsg'),
        'XPixelSize': obj.X_res,
        'YPixelSize': obj.Y_res,
        'cen_lat': obj.cen_lat,
        'cen_lon': obj.cen_lon,
    }

    return run_info


def runGeogridOptical(info, info1, dem, dhdx, dhdy, vx, vy, srx, sry, csminx, csminy, csmaxx, csmaxy, ssm, **kwargs):
    '''
    Wire and run geogrid.
    '''

    import isce
    from components.contrib.geo_autoRIFT.geogrid import GeogridOptical
#    from geogrid import GeogridOptical

    from osgeo import gdal
    dem_info = gdal.Info(dem, format='json')

    obj = GeogridOptical()

    obj.startingX = info.startingX
    obj.startingY = info.startingY
    obj.XSize = info.XSize
    obj.YSize = info.YSize
    from datetime import date
    import numpy as np
    d0 = date(np.int(info.time[0:4]),np.int(info.time[4:6]),np.int(info.time[6:8]))
    d1 = date(np.int(info1.time[0:4]),np.int(info1.time[4:6]),np.int(info1.time[6:8]))
    date_dt_base = d1 - d0
    obj.repeatTime = date_dt_base.total_seconds()
#    obj.repeatTime = (info1.time - info.time) * 24.0 * 3600.0
    obj.numberOfLines = info.numberOfLines
    obj.numberOfSamples = info.numberOfSamples
    obj.nodata_out = -32767
    obj.chipSizeX0 = 240
    obj.gridSpacingX = dem_info['geoTransform'][1]

    obj.dat1name = info.filename
    obj.demname = dem
    obj.dhdxname = dhdx
    obj.dhdyname = dhdy
    obj.vxname = vx
    obj.vyname = vy
    obj.srxname = srx
    obj.sryname = sry
    obj.csminxname = csminx
    obj.csminyname = csminy
    obj.csmaxxname = csmaxx
    obj.csmaxyname = csmaxy
    obj.ssmname = ssm
    obj.winlocname = "window_location.tif"
    obj.winoffname = "window_offset.tif"
    obj.winsrname = "window_search_range.tif"
    obj.wincsminname = "window_chip_size_min.tif"
    obj.wincsmaxname = "window_chip_size_max.tif"
    obj.winssmname = "window_stable_surface_mask.tif"
    obj.winro2vxname = "window_rdr_off2vel_x_vec.tif"
    obj.winro2vyname = "window_rdr_off2vel_y_vec.tif"
    obj.winsfname = "window_scale_factor.tif"
    ##dt-varying search range scale (srs) rountine parameters
#    obj.srs_dt_unity = 32
#    obj.srs_max_scale = 10
#    obj.srs_max_search = 20000
#    obj.srs_min_search = 0

    obj.runGeogrid()

    run_info = {
        'chipsizex0': obj.chipSizeX0,
        'gridspacingx': obj.gridSpacingX,
        'vxname': vx,
        'vyname': vy,
        'sxname': kwargs.get('dhdxs'),
        'syname': kwargs.get('dhdys'),
        'maskname': kwargs.get('sp'),
        'xoff': obj.pOff,
        'yoff': obj.lOff,
        'xcount': obj.pCount,
        'ycount': obj.lCount,
        'dt': obj.repeatTime,
        'epsg': kwargs.get('epsg'),
        'XPixelSize': obj.X_res,
        'YPixelSize': obj.Y_res,
        'cen_lat': obj.cen_lat,
        'cen_lon': obj.cen_lon,
    }

    return run_info

def main():
    '''
    Main driver.
    '''

    inps = cmdLineParse()

    if inps.optical_flag == 1:
        metadata_m, metadata_s = coregisterLoadMetadataOptical(inps.indir_m, inps.indir_s)
        runGeogridOptical(metadata_m, metadata_s, inps.demfile, inps.dhdxfile, inps.dhdyfile, inps.vxfile, inps.vyfile, inps.srxfile, inps.sryfile, inps.csminxfile, inps.csminyfile, inps.csmaxxfile, inps.csmaxyfile, inps.ssmfile)
    else:
        if inps.parse:
            metadata_m = loadParsedata(inps.indir_m,inps.buffer)
            metadata_s = loadParsedata(inps.indir_s,inps.buffer)
        else:
            metadata_m = loadMetadata(inps.indir_m,inps.buffer)
            metadata_s = loadMetadata(inps.indir_s,inps.buffer)
        runGeogrid(metadata_m, metadata_s, inps.demfile, inps.dhdxfile, inps.dhdyfile, inps.vxfile, inps.vyfile, inps.srxfile, inps.sryfile, inps.csminxfile, inps.csminyfile, inps.csmaxxfile, inps.csmaxyfile, inps.ssmfile)


if __name__ == '__main__':
    main()
