import shutil
import pandas as pd
import json
from landsatxplore.api import API
from pathlib import Path
from landsatxplore.earthexplorer import EarthExplorer
from Landsat8.landsat8_utils import create_raster_stack
import os
from osgeo import gdal


# TODO: DESCRIBE WHERE THE FILES SHOULD BE :
#   - kml file
#   - locations (path/row) file

def download_region_data(region, user, passwd, location_file_path = "location_data.json") :
    """
    Downloads tiff files from earthexplorer for a single region (given by region name)
    The resulting folder structure is one image per row/path combination per year-month folder

    Each year-month contains the tiffs to reconstruct the entire region for that time-period
    """

    username = user
    password = passwd
    api = API(username, password)
    ee = EarthExplorer(username, password)
    import shutil

    with open(location_file_path) as location_file :
        locations = json.load(location_file)
        regions = list(locations.keys())
        
        # Get the coordinates of the defining polygon to do scene search
        with open("data/" + region + "/" + region + ".kml") as kml_file :
            for line in kml_file.readlines() :
                if "<Polygon>" in line:
                    line = line.replace("<Polygon><outerBoundaryIs><LinearRing><coordinates>", "")
                    line = line.replace("</coordinates></LinearRing></outerBoundaryIs></Polygon>", "")
                    coordinate_pairs = line.strip().split(" ")
                    coordinate_pairs = [pair.split(",") for pair in coordinate_pairs]

        all_scenes = []
            
            # Get all scenes touching the polygon
        for coordinate_pair in coordinate_pairs:
            longi = float(coordinate_pair[0])
            lati = float(coordinate_pair[1])
            scenes_search = api.search(
                dataset='landsat_ot_c2_l1',
                longitude=longi,
                latitude=lati,
                max_results=50000
            )

            all_scenes.extend(scenes_search)

        # Get the path/row pairs for the scenes that compose the region entirely
        relevant_scenes = []
        path_row_pairs = locations[region]["path_row_pairs"]
        for path_row_pair in path_row_pairs :
            path = path_row_pair[0]
            row = path_row_pair[1]

            for scene in all_scenes :
                if scene["wrs_path"] == path and scene["wrs_row"] == row : 
                    if scene not in relevant_scenes :
                        relevant_scenes.append(scene)

        collected = []
        for scene in relevant_scenes:
            date = scene["acquisition_date"].date()
            path = scene["wrs_path"]
            row = scene["wrs_row"]

            info = str(date.year) + "_" + str(date.month) + "_" + str(path) + "_" + str(row)

            if info not in collected :
                path = "./data/" + region + "/" + str(date.year) + "_" + str(date.month)+ "/"
                Path(path).mkdir(exist_ok=True)
                ee.download(scene["entity_id"], path)
                collected.append(info)


def process_year_month_folder(region, year, month, delete_after = False) :
    """
    1st - creates raster stacks from the downloaded data in the folders (after unzipping)
    2nd - crops all the raster stacks in the folder, according to the corresponding KML file
    3rd - it joins the resulting rasters into a single one to reconstruct the entire region
    """

    path = "./data/" + str(region) + str(year) + "_" + str(month) + "/"

   
    Path(path + "/clipped/").mkdir(exist_ok=True)

    create_raster_stack(path, region)

    for (dirpath, dirnames, filenames) in os.walk(path + "raster_stack") :
        for stack in filenames:
            OutTile = gdal.Warp(path  + "/clipped/" + stack, 
                        path + "raster_stack/" + stack, 
                        cutlineDSName="./data/" + region + "/" + region + '.kml',
                        cropToCutline=True,
                        dstNodata = 0)

            OutTile = None

    if delete_after :
        shutil.rmtree(path + "raster_stack/")