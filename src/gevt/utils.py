import json
import os
import sys
import traceback
from pathlib import Path


def get_set_local_dir(basename='pymodaq_local') -> Path:
    if 'win32' in sys.platform:
        local_path = os.path.join(os.environ['HOMEDRIVE'] + os.environ['HOMEPATH'], basename)
    else:
        local_path = os.path.join(os.environ['PATH'], basename)

    if not os.path.isdir(local_path):
        os.makedirs(local_path)

    return Path(local_path)


def getLineInfo():
    """get information about where the Exception has been triggered"""
    tb = sys.exc_info()[2]
    res = ''
    for t in traceback.format_tb(tb):
        res += t
    return res


def import_points_geojson(filepath):
    path = Path(filepath)
    signaleurs = []
    if 'geojson' in path.suffix:
        with open(filepath) as file:
            data = json.load(file)

            for feat in data['features']:
                if feat['type'] == 'Feature':
                    if feat['geometry']['type'] == 'Point':
                        if 'description' not in feat['properties']:
                            desc = ''
                        else:
                            desc = feat['properties']['description']
                        sig = dict(name=feat['properties']['name'],
                                   coordinates=', '.join([str(co) for co in feat['geometry']['coordinates'][1::-1]]),
                                   description=desc)
                        signaleurs.append(sig)
    return signaleurs


def odd_even(x):
    """
		odd_even tells if a number is odd (return True) or even (return False)

		Parameters
		----------
		x: the integer number to test

		Returns
		-------
		bool : boolean
    """
    if int(x) % 2 == 0:
        bool = False
    else:
        bool = True
    return bool


def get_overlap(a, b):
    return min(a[1], b[1]) - max(a[0], b[0])
