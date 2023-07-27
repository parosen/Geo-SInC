# Intro to Preparing Data for Stack Processing

**Resource:** stackStripMap and topsStack videos linked on syllabus

**Expected Outcome:** Learn how to prepare stacks from scratch, not relying on ARIA tools.  

## [ISCE2/topsStack](https://github.com/isce-framework/isce2/blob/main/contrib/stack/topsStack/README.md) demonstration

### 1. Installation

```bash
# load the conda environment for isce2
conda activate unavco

# setup path for topsStack
# $ISCE_STACK is set by conda
export PATH=${PATH}:${ISCE_STACK}/topsStack

# test
stackSentinel.py -h
```

### 2. Setup auxliary directory

```bash
cd ~/bak
mkdir aux; cd aux
mkdir aux_cal aux_poeorb
```

### 3. Download S1 data from ASF using the [web browser](https://search.asf.alaska.edu/#/) or [SSARA](https://www.unavco.org/gitlab/unavco_public/ssara_client)

Example AOI / bounding box in SNWE: 32.7,35,-117,-114.5

```bash
cd ~/data-marmot/test/SaltonSeaSenDT173
mkdir SLC; cd SLC
~/tools/utils/SSARA/ssara_federated_query.py -p SENTINEL-1A,SENTINEL-1B -r 173 -b '32.7,35,-117,-114.5' --print
~/tools/utils/SSARA/ssara_federated_query.py -p SENTINEL-1A,SENTINEL-1B -r 173 -b '32.7,35,-117,-114.5' --kml
~/tools/utils/SSARA/ssara_federated_query.py -p SENTINEL-1A,SENTINEL-1B -r 173 -b '32.7,35,-117,-114.5' --download --parallel=4
```

### 4. DEM

```bash
cd ~/data-marmot/test/SaltonSeaSenDT173
mkdir DEM; cd DEM
sardem --bbox -118 31 -113 36 --data COP -isce
# sardem --bbox -118 31 -113 36 --data COP -isce -o copernicus.dem   # pre-stage
# equivalent to $ISCE_HOME/applications/dem.py
```

### 5. Run stackSentinel.py

Tips: use the same SNWE/AOI/bbox in "3. data search/download" and "5. run", to avoid the potential descrepency between the downloaded and needed data.

```bash
cd ~/data-marmot/test/SaltonSeaSenDT173
stackSentinel.py -s ./SLC -o ~/bak/aux/aux_poeorb -a ~/bak/aux/aux_cal --dem ./DEM/copernicus.dem --coregistration geometry -n '1 2 3' --bbox '32.7 35 -117 -114.5' -W interferogram -c 3 --azimuth_looks 5 --range_looks 15 -f 0.5 -u snaphu
```

Show the `run_files` and `configs` folder, and how to execute the run files.

Show the final results in `~/data-marmot/offset4motion/SaltonSeaSenDT173/merged`. This point is equivalent to the ariaDownload/TSsetup result.

Show the mintpy [input example for isce2/topsStack](https://mintpy.readthedocs.io/en/latest/dir_structure/#isce_topsstack).
