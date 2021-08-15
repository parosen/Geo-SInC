# asf_notebook.py
# Alex Lewandowski
# 4-15-2021
# Module of Alaska Satellite Facility OpenSARLab Jupyter Notebook helper functions


import os  # for chdir, getcwd, path.exists
import re
from typing import List
import requests  # for post, get
from getpass import getpass  # used to input URS creds and add to .netrc
import zipfile  # for extractall, ZipFile, BadZipFile
from datetime import datetime, date
import glob
import sys
import subprocess

from osgeo import gdal  # for Open
import numpy as np
import pandas as pd

from matplotlib.widgets import RectangleSelector
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size': 12})

from IPython.display import clear_output
from IPython.display import Markdown
from IPython.display import display

import ipywidgets as widgets
from ipywidgets import Layout

from asf_hyp3 import API, LoginError  # for get_products, get_subscriptions, login

from hyp3_sdk import HyP3
from hyp3_sdk import asf_search
from hyp3_sdk import Batch

#######################
#  Utility Functions  #
#######################


def path_exists(path: str) -> bool:
    """
    Takes a string path, returns true if exists or
    prints error message and returns false if it doesn't.
    """
    assert type(path) == str, 'Error: path must be a string'

    if os.path.exists(path):
        return True
    else:
        print(f"Invalid Path: {path}")
        return False


def new_directory(path: str):
    """
    Takes a path for a new or existing directory. Creates directory
    and sub-directories if not already present.
    """
    assert type(path) == str

    if os.path.exists(path):
        print(f"{path} already exists.")
    else:
        os.makedirs(path)
        print(f"Created: {path}")
    if not os.path.exists(path):
        print(f"Failed to create path!")


def asf_unzip(output_dir: str, file_path: str):
    """
    Takes an output directory path and a file path to a zipped archive.
    If file is a valid zip, it extracts all to the output directory.
    """
    ext = os.path.splitext(file_path)[1]
    assert type(output_dir) == str, 'Error: output_dir must be a string'
    assert type(file_path) == str, 'Error: file_path must be a string'
    assert ext == '.zip', 'Error: file_path must be the path of a zip'

    if path_exists(output_dir):
        if path_exists(file_path):
            print(f"Extracting: {file_path}")
            try:
                zipfile.ZipFile(file_path).extractall(output_dir)
            except zipfile.BadZipFile:
                print(f"Zipfile Error.")
            return


def get_power_set(my_set, set_size=None):
    """
    my_set: list or set of strings
    set_size: deprecated, kept as optional for backwards compatibility
    returns: the power set of input strings
    """
    p_set = set()
    if len(my_set) > 1:
        pow_set_size = 1 << len(my_set) # 2^n
        for counter in range(0, pow_set_size):
            temp = ""
            for j in range(0, len(my_set)):
                if(counter & (1 << j) > 0):
                    if temp != "":
                        temp = f"{temp} and {my_set[j]}"
                    else:
                        temp = my_set[j]
                if temp != "":
                    p_set.add(temp)
    else:
        p_set = set(my_set)
    return p_set


def remove_nan_filled_tifs(tif_dir: str, file_names: list):
    """
    Takes a path to a directory containing tifs and
    and a list of the tif filenames.
    Deletes any tifs containing only NaN values.
    """
    assert type(tif_dir) == str, 'Error: tif_dir must be a string'
    assert len(file_names) > 0, 'Error: file_names must contain at least 1 file name'

    removed = 0
    for tiff in file_names:
        raster = gdal.Open(f"{tif_dir}{tiff}")
        if raster:
            band = raster.ReadAsArray()
            if np.count_nonzero(band) < 1:
                os.remove(f"{tif_dir}{tiff}")
                removed += 1
    print(f"GeoTiffs Examined: {len(file_names)}")
    print(f"GeoTiffs Removed:  {removed}")


def input_path(prompt):
    print(f"Current working directory: {os.getcwd()}")
    print(prompt)
    return input()


def handle_old_data(data_dir, contents):
    print(f"\n********************** WARNING! **********************")
    print(f"The directory {data_dir} already exists and contains:")
    for item in contents:
        print(f"• {item.split('/')[-1]}")
    print(f"\n\n[1] Delete old data and continue.")
    print(f"[2] Save old data and add the data from this analysis to it.")
    print(f"[3] Save old data and pick a different subdirectory name.")
    while True:
        try:
            selection = int(input("Select option 1, 2, or 3.\n"))
        except ValueError:
             continue
        if selection < 1 or selection > 3:
             continue
        return selection


#########################
#  OpenSARlab Functions #
#########################


def jupytertheme_matplotlib_format() -> bool:
    """
    If recognised jupytertheme dark mode is being used,
    reformat matplotlib settings for improved dark mode visibility.
    Return True if matplotlib settings adjusted or False if not
    """
    try:
        from jupyterthemes import jtplot
        print(f"jupytertheme style: {jtplot.infer_theme()}")
        if jtplot.infer_theme() in ('osl_dark', 'onedork'):
            plt.rcParams.update({'hatch.color': 'white'})
            plt.rcParams.update({'axes.facecolor': 'lightgrey'})
            plt.rcParams.update({'axes.labelcolor': 'white'})
            plt.rcParams.update({'xtick.color': 'lightgrey'})
            plt.rcParams.update({'ytick.color': 'lightgrey'})
            return True
    except ModuleNotFoundError:
        print("jupytertheme not installed")
        pass
    return False


###################
#  GDAL Functions #
###################

def vrt_to_gtiff(vrt: str, output: str):
    if '.vrt' not in vrt:
        print('Error: The path to your vrt does not contain a ".vrt" extension.')
        return
    if '.' not in output:
        output = f"{output}.tif"
    elif len(output) > 4 and (output[:-3] == 'tif' or output[:-4] == 'tiff'):
        print('Error: the output argument must either not contain a ' /
              'file extension, or have a "tif" or "tiff" file extension.')
        return

    cmd = f"gdal_translate -co \"COMPRESS=DEFLATE\" -a_nodata 0 {vrt} {output}"
    sub = subprocess.run(cmd, stderr=subprocess.PIPE, shell=True)
    print(str(sub.stderr)[2: -3])

#########################
#  Earthdata Auth Class #
#########################

class EarthdataLogin:

    def __init__(self, username=None, password=None):

        """
        takes user input to login to NASA Earthdata
        updates .netrc with user credentials
        returns an api object
        note: Earthdata's EULA applies when accessing ASF APIs
              Hyp3 API handles HTTPError and LoginError
        """
        err = None
        while True:
            if err: # Jupyter input handling requires printing login error here to maintain correct order of output.
                print(err)
                print("Please Try again.\n")
            if not username or not password:
                print(f"Enter your NASA EarthData username:")
                username = input()
                print(f"Enter your password:")
                password = getpass()
            try:
                api = API(username) # asf_hyp3 function
            except Exception:
                raise
            else:
                try:
                    api.login(password)
                except LoginError as e:
                    err = e
                    clear_output()
                    username = None
                    password = None
                    continue
                except Exception:
                    raise
                else:
                    clear_output()
                    print(f"Login successful.")
                    print(f"Welcome {username}.")
                    self.username = username
                    self.password = password
                    self.api = api
                    break


    def login(self):
        try:
            self.api.login(self.password)
        except LoginError:
            raise


#########################
#  Vertex API Functions #
#########################


def get_vertex_granule_info(granule_name: str, processing_level: int) -> dict:
    """
    Takes a string granule name and int processing level, and returns the granule info as json.<br><br>
    preconditions:
    Requires AWS Vertex API authentification (already logged in).
    Requires a valid granule name.
    Granule and processing level must match.
    """
    assert type(granule_name) == str, 'Error: granule_name must be a string.'
    assert type(processing_level) == str, 'Error: processing_level must be a string.'

    vertex_API_URL = "https://api.daac.asf.alaska.edu/services/search/param"
    try:
        response = requests.post(
            vertex_API_URL,
            params=[('granule_list', granule_name), ('output', 'json'),
                    ('processingLevel', processing_level)]
        )
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        print(e)
        sys.exit(1)
    else:
        if len(response.json()) > 0:
            json_response = response.json()[0][0]
            return json_response
        else:
            print("get_vertex_granule_info() failed.\ngranule/processing level mismatch.")


#########################
#  Hyp3v1 API Functions #
#########################


def get_hyp3_subscriptions(login: EarthdataLogin, group_id=None) -> dict:
    """
    Takes an EarthdataLogin object and returns a list of associated, enabled subscriptions
    Returns None if there are no enabled subscriptions associated with Hyp3 account.
    """

    assert type(login) == EarthdataLogin, 'Error: login must be an EarthdataLogin object'

    while True:
        subscriptions = login.api.get_subscriptions(enabled=True, group_id=group_id)
        try:
            if subscriptions['status'] == 'ERROR' and \
                  subscriptions['message'] == 'You must have a valid API key':
                creds = login.api.reset_api_key()
                login.api.api = creds['api_key']
        except (KeyError, TypeError):
            break
    subs = []
    if not subscriptions:
        if not group_id:
            print(f"Found no subscriptions for Hyp3 user: {login.username}")
        else:
            print(f"Found no subscriptions for Hyp3 user: {login.username}, in group: {group_id}")
    else:
        for sub in subscriptions:
            subs.append(f"{sub['id']}: {sub['name']}")
    return subs


def get_subscription_products_info(subscription_id: int, login: EarthdataLogin, group_id=None) -> list:

    assert type(subscription_id) == str, f'Error: subscription_id must be a string, not a {type(subscription_id)}'
    assert type(login) == EarthdataLogin, f'Error: login must be an EarthdataLogin object, not a {type(login)}'

    products = []
    page_count = 0
    while True:
        product_page = login.api.get_products(
            sub_id=subscription_id, page=page_count, page_size=100, group_id=group_id)
        try:
            if product_page['status'] == 'ERROR'and \
                  product_page['message'] == 'You must have a valid API key':
                creds = login.api.reset_api_key()
                login.api.api = creds['api_key']
                continue
        except (KeyError, TypeError):
            page_count += 1
            pass
        if not product_page:
            break
        for product in product_page:
            products.append(product)
    return products


def get_subscription_granule_names_ids(subscription_id: int, login: EarthdataLogin) -> dict:

    assert type(subscription_id) == str, f'Error: subscription_id must be a string, not a {type(subscription_id)}'
    assert type(login) == EarthdataLogin, f'Error: login must be an EarthdataLogin object, not a {type(login)}'

    jobs_list = login.api.get_jobs(sub_id=subscription_id)
    granules = dict()
    for job in jobs_list:
        granules.update({job['granule']: job['id']})
    return granules


def get_wget_cmd(url: str, login: EarthdataLogin) -> str:
    cmd = f"wget -c -q --show-progress --http-user={login.username} --http-password={login.password} {url}"
    return cmd


#########################
#  Hyp3v2 API Functions #
#########################

def get_RTC_projects(hyp3):
    return hyp3.my_info()['job_names']

def get_job_dates(jobs: List[str]) -> List[str]:
    dates = set()
    for job in jobs:
        for granule in job.job_parameters['granules']:
            dates.add(date_from_product_name(granule).split('T')[0])
    return list(dates)

def filter_jobs_by_date(jobs, date_range):
    remaining_jobs = Batch()
    for job in jobs:
        for granule in job.job_parameters['granules']:
            dt = date_from_product_name(granule).split('T')[0]
            aquistion_date = date(int(dt[:4]), int(dt[4:6]), int(dt[-2:]))
            if date_range[0] <= aquistion_date <= date_range[1]:
                remaining_jobs += job
                break
    return remaining_jobs

def get_paths_orbits(jobs):
    vertex_API_URL = "https://api.daac.asf.alaska.edu/services/search/param"
    for job in jobs:
        granule_metadata = asf_search.get_metadata(job.job_parameters['granules'][0])
        job.path = granule_metadata['path']
        job.orbit_direction = granule_metadata['flightDirection']
    return jobs

def filter_jobs_by_path(jobs, paths):
    if 'All Paths' in paths:
        return jobs
    remaining_jobs = Batch()
    for job in jobs:
        if job.path in paths:
            remaining_jobs += job
    return remaining_jobs

def filter_jobs_by_orbit(jobs, orbit_direction):
    remaining_jobs = Batch()
    for job in jobs:
        if job.orbit_direction == orbit_direction:
            remaining_jobs += job
    return remaining_jobs


#######################################
#   Product Related Utility Functions #
#######################################

def get_product_info(granules: dict, products_info: list, date_range: list) -> dict:
    paths = []
    directions = []
    urls = []
    vertex_API_URL = "https://api.daac.asf.alaska.edu/services/search/param"
    for granule_name in granules:
        dt = date_from_product_name(granule_name)
        if dt:
            dt = dt.split('T')[0]
        else:
            continue
        if date(int(dt[:4]), int(dt[4:6]), int(dt[-2:])) >= date_range[0]:
            if date(int(dt[:4]), int(dt[4:6]), int(dt[-2:])) <= date_range[1]:
                parameters = [('granule_list', granule_name), ('output', 'json')]
                try:
                    response = requests.post(
                        vertex_API_URL,
                        params=parameters,
                        stream=True
                    )
                except requests.exceptions.RequestException as e:
                    print(e)
                    sys.exit(1)
                json_response = None
                if response.json()[0]:
                    json_response = response.json()[0][0]
                local_queue_id = granules[granule_name]
                for p_info in products_info:
                    if p_info['local_queue_id'] == local_queue_id:
                        try:
                            paths.append(json_response['track'])
                            directions.append(json_response['flightDirection'])
                            urls.append(p_info['url'])
                        except TypeError:
                            print(f"TypeError: json_response for {granule_name}: {json_response}")
                            pass
                        break
    return {'paths': paths, 'directions': directions, 'urls': urls}

def date_from_product_name(product_name: str) -> str:
    regex = "\w[0-9]{7}T[0-9]{6}"
    results = re.search(regex, product_name)
    if results:
        return results.group(0)
    else:
        return None

def get_products_dates(products_info: list) -> list:
    dates = []
    for info in products_info:
        date_regex = "\w[0-9]{7}T[0-9]{6}"
        date_strs = re.findall(date_regex, info['granule'])
        if date_strs:
            for d in date_strs:
                dates.append(d[0:8])
    dates.sort()
    dates = list(set(dates))
    return dates

# get_products_dates_insar will be deprecated in the
# near future as it is now duplicted in get_products_dates
def get_products_dates_insar(products_info: list) -> list:
    dates = []
    for info in products_info:
        date_regex = "\w[0-9]{7}T[0-9]{6}"
        date_strs = re.findall(date_regex, info['granule'])
        if date_strs:
            for d in date_strs:
                dates.append(d[0:8])
    dates.sort()
    dates = list(set(dates))
    return dates


######################################
#  Jupyter Notebook Widget Functions #
######################################


def gui_date_picker(dates: list) -> widgets.SelectionRangeSlider:
    start_date = datetime.strptime(min(dates), '%Y%m%d')
    end_date = datetime.strptime(max(dates), '%Y%m%d')
    date_range = pd.date_range(start_date, end_date, freq='D')
    options = [(date.strftime(' %m/%d/%Y '), date) for date in date_range]
    index = (0, len(options)-1)

    selection_range_slider = widgets.SelectionRangeSlider(
    options = options,
    index = index,
    description = 'Dates',
    orientation = 'horizontal',
    layout = {'width': '500px'})
    return(selection_range_slider)


def get_slider_vals(selection_range_slider: widgets.SelectionRangeSlider) -> list:
    '''Returns the minimum and maximum dates retrieved from the
    interactive time slider.

    Parameters:
    - selection_range_slider: Handle of the interactive time slider
    '''
    [a,b] = list(selection_range_slider.value)
    slider_min = a.to_pydatetime()
    slider_max = b.to_pydatetime()
    return[slider_min, slider_max]


def get_polarity_from_path(path: str) -> str:
    """
    Takes a path to a HyP3 product containing its polarity in its filename
    Returns the polarity string or none if not found
    """
    path = os.path.basename(path)
    regex = "(v|V|h|H){2}"
    return re.search(regex, path).group(0)


def get_RTC_polarizations(base_path: str) -> list:
    """
    Takes a string path to a directory containing RTC product directories
    Returns a list of present polarizations
    """
    assert type(base_path) == str, 'Error: base_path must be a string.'
    assert os.path.exists(base_path), f"Error: select_RTC_polarization was passed an invalid base_path, {base_path}"
    paths = []
    pths = glob.glob(f"{base_path}/*/*.tif")
    if len(pths) > 0:
        for p in pths:
            filename = os.path.basename(p)
            polar_fname = re.search("^\w[\--~]{5,300}(_|-)(vv|VV|vh|VH|hh|HH|hv|HV).(tif|tiff)$", filename)
            if polar_fname:
                paths.append(polar_fname.string.split('.')[0][-2:])
    if len(paths) > 0:
        return list(set(paths))
    else:
        print(f"Error: found no available polarizations.")


def select_parameter(things, description=""):
    return widgets.RadioButtons(
        options=things,
        description=description,
        disabled=False,
        layout=Layout(min_width='800px')
    )



def select_mult_parameters(things, description=""):
    height = len(things) * 19
    return widgets.SelectMultiple(
        options=things,
        description=description,
        disabled=False,
        layout=widgets.Layout(height=f"{height}px", width='175px')
    )


########################################
#  Subset AOI Selector #
########################################

class AOI_Selector:
    def __init__(self,
                 image,
                 fig_xsize=None, fig_ysize=None,
                 cmap=plt.cm.gist_gray,
                 vmin=None, vmax=None
                ):
        display(Markdown(f"<text style=color:blue><b>Area of Interest Selector Tips:\n</b></text>"))
        display(Markdown(f'<text style=color:blue>- This plot uses "matplotlib notebook", whereas the other plots in this notebook use "matplotlib inline".</text>'))
        display(Markdown(f'<text style=color:blue>-  If you run this cell out of sequence and the plot is not interactive, rerun the "%matplotlib notebook" code cell.</text>'))
        display(Markdown(f'<text style=color:blue>- Use the pan tool to pan with the left mouse button.</text>'))
        display(Markdown(f'<text style=color:blue>- Use the pan tool to zoom with the right mouse button.</text>'))
        display(Markdown(f'<text style=color:blue>- You can also zoom with a selection box using the zoom to rectangle tool.</text>'))
        display(Markdown(f'<text style=color:blue>- To turn off the pan or zoom to rectangle tool so you can select an AOI, click the selected tool button again.</text>'))

        display(Markdown(f'<text style=color:darkred><b>IMPORTANT!</b></text>'))
        display(Markdown(f'<text style=color:darkred>- Upon loading the AOI selector, the selection tool is already active.</text>'))
        display(Markdown(f'<text style=color:darkred>- Click, drag, and release the left mouse button to select an area.</text>'))
        display(Markdown(f'<text style=color:darkred>- The square tool icon in the menu is <b>NOT</b> the selection tool. It is the zoom tool.</text>'))
        display(Markdown(f'<text style=color:darkred>- If you select any tool, you must toggle it off before you can select an AOI</text>'))
        self.image = image
        self.x1 = None
        self.y1 = None
        self.x2 = None
        self.y2 = None
        if not vmin:
            self.vmin = np.nanpercentile(self.image, 1)
        else:
            self.vmin = vmin
        if not vmax:
            self.vmax=np.nanpercentile(self.image, 99)
        else:
            self.vmax = vmax
        if fig_xsize and fig_ysize:
            self.fig, self.current_ax = plt.subplots(figsize=(fig_xsize, fig_ysize))
        else:
            self.fig, self.current_ax = plt.subplots()
        self.fig.suptitle('Area-Of-Interest Selector', fontsize=16)
        self.current_ax.imshow(self.image, cmap=plt.cm.gist_gray, vmin=self.vmin, vmax=self.vmax)


        def toggle_selector(self, event):
            print(' Key pressed.')
            if event.key in ['Q', 'q'] and toggle_selector.RS.active:
                print(' RectangleSelector deactivated.')
                toggle_selector.RS.set_active(False)
            if event.key in ['A', 'a'] and not toggle_selector.RS.active:
                print(' RectangleSelector activated.')
                toggle_selector.RS.set_active(True)

        toggle_selector.RS = RectangleSelector(self.current_ax, self.line_select_callback,
                                               drawtype='box', useblit=True,
                                               button=[1, 3],  # don't use middle button
                                               minspanx=5, minspany=5,
                                               spancoords='pixels',
                                               rectprops = dict(facecolor='red', edgecolor = 'yellow',
                                                                alpha=0.3, fill=True),
                                               interactive=True)
        plt.connect('key_press_event', toggle_selector)

    def line_select_callback(self, eclick, erelease):
        'eclick and erelease are the press and release events'
        self.x1, self.y1 = eclick.xdata, eclick.ydata
        self.x2, self.y2 = erelease.xdata, erelease.ydata
        print("(%3.2f, %3.2f) --> (%3.2f, %3.2f)" % (self.x1, self.y1, self.x2, self.y2))
        print(" The button you used were: %s %s" % (eclick.button, erelease.button))
