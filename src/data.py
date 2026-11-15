from multiprocessing import pool
import threading
import time
from tracemalloc import start
from urllib import response
import uuid
import astropy
import astropy.units as u
import astropy.visualization
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from astroquery.ipac.irsa import Irsa
from astropy.visualization import AsinhStretch, ZScaleInterval, ImageNormalize
import requests
import os 
import matplotlib.pyplot as plt
import json

S3_URL = "https://{bucket_name}.s3.{region}.amazonaws.com/{key}"
IRSA_PREFIX = "/ibe/data/spherex/"

_session = requests.Session()
_session.mount("https://", requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=3))

def cloud_url(row):
    try:
        return S3_URL.format(**json.loads(row["cloud_access"])["aws"])
    except Exception as e:
        url = row["access_url"]
        if IRSA_PREFIX in url:
            return ("https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com" + url.split(IRSA_PREFIX, 1)[1])

def download_group(ra, dec):
    directory = f'data/{ra}-{dec}'
    if not os.path.exists(directory):
        os.makedirs(directory)

    if len(os.listdir(directory)) > 0:
        print(f"Directory {directory} already exists and is not empty. Skipping download.")
        return

    # Looks for results
    coord = SkyCoord(ra=150.7818, dec=3.3502, unit='deg', frame='icrs')

    print("Querying IRSA for images...")

    while True:
        try:
            results = Irsa.query_sia(pos=(coord, 1.0 * u.arcmin), collection='spherex_dr1')
            break
        except Exception as e:
            print(f"Error occurred: {e}. Retrying...")

    print(f"{len(results)} results found for RA: {ra}, Dec: {dec}")

    # Downloads images
    if len(results) == 0:
        return

    index = 0

    start_time = time.time()

    max_threads = 32

    # yield len(results) # pass how many images are need to process

    for result in results:
        while threading.active_count() > max_threads:
            time.sleep(0.1)
        # yield 1
        threading.Thread(target=_download_image_thread(result)).start()

def _download_group_thread(ra, dec):
    def thread():
        download_group(ra, dec)
    return thread

def _download_image_thread(result):
    def thread():
        image_url = cloud_url(result)
        name = result['obs_id'].split("_")[0]

        wl = round((result['em_min'] * 10**6 + result['em_max'] * 10**6) / 2, 4) # average wavelength in the image

        filename = f"data/{ra}-{dec}/{name}/{wl}.png"

        if os.path.exists(f'data/{ra}-{dec}/{name}/{wl}.png'):
            print(f"Image {filename} already exists. Skipping download.")
            return

        print('starting download')

        with fits.open(image_url, use_fsspec=True, fsspec_kwargs={"block_size": 2_000_000, "cache_type": "none"}) as h:
            image_data = h[2].data

        print('download finished')

        os.makedirs(os.path.dirname(filename), exist_ok=True)

        norm = ImageNormalize(image_data, interval=ZScaleInterval(), stretch=AsinhStretch())
        tmp = filename + ".part"
        plt.imsave(tmp, norm(image_data), cmap='magma', origin='lower', format='png')
        os.replace(tmp, filename)

        print(f'finished image {filename}')
    return thread

def get_image(ra, dec):
    final = {}
    if not os.path.exists(f'data/{ra}-{dec}'):
        print('starting download')
        # threading.Thread(target=_download_group_thread(ra, dec)).start()
        download_group(ra, dec)
        return

    dates = os.listdir(f'data/{ra}-{dec}')
    dates.sort()
    for date in dates:
        if not os.path.isdir(f'data/{ra}-{dec}/{date}'):
            continue
        final[date] = []
        wavelengths = os.listdir(f'data/{ra}-{dec}/{date}')
        for wavelength in wavelengths:
            final[date].append(float(wavelength.replace('.png', ''))) # type: ignore
    
        final[date].sort()

    return final

if __name__ == "__main__":
    ra = 133.795129
    dec = -7.245147
    print(get_image(ra, dec))

        