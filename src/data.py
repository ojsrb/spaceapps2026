import threading
import time
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astroquery.ipac.irsa import Irsa
from astropy.visualization import AsinhStretch, ZScaleInterval, ImageNormalize
import requests
import os 
import matplotlib.pyplot as plt
import json
import queue
from astropy.visualization import simple_norm

S3_URL = "https://{bucket_name}.s3.{region}.amazonaws.com/{key}"
IRSA_PREFIX = "/ibe/data/spherex/"

# Written into a coordinate folder once every image for that position is on disk. The
# folder is only reused when this manifest exists and every image it lists is still
# there, so an interrupted run gets retried while a finished one is never downloaded
# again. It replaces the old ".incomplete" marker, which could survive a crash and make
# a full folder look unfinished forever.
MANIFEST = ".manifest.json"
LEGACY_INCOMPLETE_MARKER = ".incomplete"

IRSA_ATTEMPTS = 10
IRSA_RETRY_DELAY = 0.1 # seconds, multiplied by the attempt number

_session = requests.Session()
_session.mount("https://", requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=3))


def _image_paths(directory):
    """Yield the path of every finished image below a coordinate folder."""
    if not os.path.isdir(directory):
        return
    for date in os.listdir(directory):
        date_dir = os.path.join(directory, date)
        if not os.path.isdir(date_dir):
            continue
        for filename in os.listdir(date_dir):
            if filename.endswith(".png"):
                yield os.path.join(date_dir, filename)

def _read_manifest(directory):
    """Images a finished download recorded, or None when the directory has no manifest."""
    try:
        with open(os.path.join(directory, MANIFEST), encoding="utf-8") as manifest_file:
            images = json.load(manifest_file)["images"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(images, list):
        return None
    return images


def _write_manifest(directory):
    """Record the images that are on disk now, which marks the download as finished."""
    images = sorted(os.path.relpath(path, directory) for path in _image_paths(directory))
    manifest = os.path.join(directory, MANIFEST)
    partial = manifest + ".part"
    with open(partial, "w", encoding="utf-8") as manifest_file:
        json.dump({"images": images}, manifest_file)
    os.replace(partial, manifest)

    # Left behind by older versions. The manifest is what marks a folder complete now, so
    # a leftover marker can no longer trigger a fresh download.
    try:
        os.remove(os.path.join(directory, LEGACY_INCOMPLETE_MARKER))
    except OSError:
        pass


def is_complete(directory):
    """A coordinate folder is reusable when its manifest and every image in it are there."""
    images = _read_manifest(directory)
    if not images:
        return False
    for image in images:
        path = os.path.join(directory, image)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            return False
    return True


class ImageSet(dict):
    """dates -> wavelengths, plus how many images could not be downloaded."""

    failed = 0

def cloud_url(row):
    """Best effort download URL for an image row, or None when there is no usable location."""
    try:
        return S3_URL.format(**json.loads(row["cloud_access"])["aws"])
    except (KeyError, IndexError, TypeError, ValueError):
        pass # no S3 mirror in this row, fall back to the IRSA path

    try:
        url = row["access_url"]
    except (KeyError, IndexError, TypeError):
        return None

    if isinstance(url, str) and IRSA_PREFIX in url:
        return "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/" + url.split(IRSA_PREFIX, 1)[1]

    return None

def _image_target(result, ra, dec):
    """Where a result should be saved, as (path on disk, download URL)."""
    image_url = cloud_url(result)
    if not image_url:
        raise ValueError(f"No download URL for {result['obs_id']}")
    date = str(result['obs_id']).split("_")[0]
    wl = round((result['em_min'] * 10**6 + result['em_max'] * 10**6) / 2, 4)
    return f"data/{ra}-{dec}/{date}/{wl}.png", image_url


def download_group(ra, dec):
    directory = f'data/{ra}-{dec}'
    os.makedirs(directory, exist_ok=True)

    if is_complete(directory):
        print(f"Directory {directory} is already complete. Skipping download.")
        return 0

    # Looks for results
    coord = SkyCoord(ra=ra, dec=dec, unit='deg', frame='icrs')

    print("Querying IRSA for images...")

    results = None
    last_error = None
    for attempt in range(1, IRSA_ATTEMPTS + 1):
        try:
            results = Irsa.query_sia(pos=(coord, 1.0 * u.arcmin), collection='spherex_dr1')
            break
        except Exception as e: # the archive is flaky, so give up after a few attempts
            last_error = e
            print(f"Error occurred: {e}. Attempt {attempt}/{IRSA_ATTEMPTS}, retrying...")
            time.sleep(IRSA_RETRY_DELAY * attempt)

    if results is None:
        raise RuntimeError(f"Could not reach the IRSA archive after {IRSA_ATTEMPTS} attempts: {last_error}")

    print(f"{len(results)} results found for RA: {ra}, Dec: {dec}")

    # Downloads images
    if len(results) == 0:
        return 0 # a valid empty result, nothing is missing

    # Only images that are not on disk from an earlier submit are actually fetched, so a
    # retry after a partial failure never downloads the same picture twice.
    pending = {}
    failed = 0
    for result in results:
        try:
            filename, image_url = _image_target(result, ra, dec)
        except (KeyError, IndexError, TypeError, ValueError) as e:
            failed += 1
            print(f"DOWNLOAD SKIPPED: {e}")
            continue
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            continue # already cached
        pending[filename] = image_url # one file per date + wavelength

    pending = list(pending.items())
    next_index = 0
    max_threads = 32
    done = queue.Queue() # threads report back through this queue
    threads_running = []

    if pending:
        yield len(pending) # pass the number of photos still to download

        # Start downloading images via threads
        while next_index < min(max_threads, len(pending)): # Keep it at the min threads and finish when done
            thread = threading.Thread(
                target = _download_image_thread,
                args = (*pending[next_index], done)
            )
            thread.start()
            threads_running.append(thread)
            next_index += 1

        # Record completed threads
        completed = 0
        while completed < len(pending):
            error = done.get() # blocks until one of the running threads finishes
            if error is not None:
                failed += 1
                print(f"DOWNLOAD FAILED: {error}")
            completed += 1

            # Start the next download now that a thread slot is free
            if next_index < len(pending):
                thread = threading.Thread(
                    target = _download_image_thread,
                    args = (*pending[next_index], done)
                )
                thread.start()
                threads_running.append(thread)
                next_index += 1

            yield completed # tell the loader bar how many are done

    #Exit threads
    for thread in threads_running:
        thread.join()

    if failed:
        # No manifest is written, so the next submit retries only the missing images
        print(f"{failed} of {len(results)} images failed for {directory}, it will be retried.")
    else:
        _write_manifest(directory) # only now is the folder known to be complete

    return failed

def _download_image_thread(filename, image_url, done):
    error = None # I mean... hopefully there's no errors with 1 line...
    tmp = None

    try:
        print(f'starting download of {filename}')

        with fits.open(image_url, use_fsspec=True, fsspec_kwargs={"block_size": 2_000_000, "cache_type": "none"}) as h:
            image_data = h[2].data

        print("download finished")
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        # norm = ImageNormalize(image_data, interval=ZScaleInterval(), stretch=AsinhStretch(), vmin=0.0, vmax=0.5)
        norm = simple_norm(image_data, stretch='asinh', percent=99.0)

        tmp = filename + ".part"
        plt.imsave(tmp, norm(image_data), cmap='gray', origin='lower', format='png')
        os.replace(tmp, filename)
        tmp = None
        print(f'finished image {filename}')

    except Exception as e:
        error = e
        print(f"Error download image: {e}")

    finally:
        if tmp is not None and os.path.exists(tmp):
            try:
                os.remove(tmp) # don't leave half written images behind
            except OSError:
                pass
        done.put(error) #say the error


def get_image(ra, dec):
    final = ImageSet()
    failed = 0
    coordinate_dir = f'data/{ra}-{dec}'

    if not is_complete(coordinate_dir):
        print('starting download')
        failed = yield from download_group(ra, dec)

    if not os.path.isdir(coordinate_dir):
        return final # the download failed before it could create anything

    dates = os.listdir(coordinate_dir)
    dates.sort()
    for date in dates:
        date_dir = os.path.join(coordinate_dir, date)
        if not os.path.isdir(date_dir):
            continue # skips the manifest and stray files like .DS_Store

        found = []
        for filename in os.listdir(date_dir):
            if not filename.endswith('.png'):
                continue # skip .part leftovers and .DS_Store
            try:
                found.append(float(filename[:-len('.png')]))
            except ValueError:
                continue # not a wavelength, ignore it

        if not found:
            continue # nothing usable for this date

        found.sort()
        final[date] = found

    final.failed = failed
    return final

if __name__ == "__main__":
    ra = 0.0
    dec = 0.0 
    gen = get_image(ra, dec)
    try:
        while True:
            print(f"Progress: {next(gen)}")
    except StopIteration as e:
        print(e.value)