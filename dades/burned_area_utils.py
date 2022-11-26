# -*- coding: utf-8 -*-
"""
Created on Wed Jul 27 20:59:36 2022

@author: Xavi Pascuet
"""

import datetime as dt
from osgeo import osr, gdal
import glob
import copy
import numpy as np
import pandas as pd
import fiona
from fiona import crs
import rasterio
from shapely.geometry import shape, mapping
from sentinelhub import (
    CRS,
    BBox,
    SHConfig,
    DataCollection,
    MimeType,
    SentinelHubRequest,
    parse_time,
    SentinelHubStatistical,
)

config = SHConfig()
def stats_to_df(stats_data):
    """ Transform Statistical API response into a pandas.DataFrame
    """
    df_data = []

    for single_data in stats_data['data']:
        df_entry = {}
        is_valid_entry = True

        df_entry['interval_from'] = parse_time(
            single_data['interval']['from']).date()
        df_entry['interval_to'] = parse_time(
            single_data['interval']['to']).date()

        for output_name, output_data in single_data['outputs'].items():
            for band_name, band_values in output_data['bands'].items():

                band_stats = band_values['stats']
                if band_stats['sampleCount'] == band_stats['noDataCount']:
                    is_valid_entry = False
                    break

                for stat_name, value in band_stats.items():
                    col_name = f'{output_name}_{band_name}_{stat_name}'
                    if stat_name == 'percentiles':
                        for perc, perc_val in value.items():
                            perc_col_name = f'{col_name}_{perc}'
                            df_entry[perc_col_name] = perc_val
                    else:
                        df_entry[col_name] = value

        if is_valid_entry:
            df_data.append(df_entry)

    return pd.DataFrame(df_data)


nbr_evalscript = """
// returns NBR masking cloud pixels
function setup() {
  return {
    input: [
      {
        bands: ["B8A", "B12", "CLM", "CLP", "dataMask"]
      }
    ],
    output: [
      {
        id: "nbr",
        bands: 1
      },
      {
        id: "masks",
        bands: ["CLM"],
        sampleType: "UINT16"
      },
      {
        id: "dataMask",
        bands: 1
      }
    ]
  }
}
function evaluatePixel(samples) {
    // cloud probability normalized to interval [0, 1]
    let CLP = samples.CLP / 255.0;
    // masking cloudy pixels
    let combinedMask = samples.dataMask
    if (samples.CLM > 0) {
        combinedMask = 0;
    }
    return {
      nbr: [index(samples.B8A, samples.B12)],
      masks: [samples.CLM],
      dataMask: [combinedMask]
    };
}
"""

evalscript_true_color = """
    //VERSION=3

    function setup() {
        return {
            input: [{
                bands: ["B02", "B03", "B04", "B8A", "B12"],
                units: "DN"
            }],
            output: {
                bands: 5,
                sampleType: "INT16"
            }
        };
    }

    function evaluatePixel(sample) {
        return [sample.B04, sample.B03, sample.B02, sample.B8A, sample.B12];
    }
"""


def get_tiffs(bbox, fire_start_day, fire_end_day):
    area_bbox = BBox(bbox, crs=CRS.WGS84)
    # Request last image pre-fire
    fire_start_day_dt = dt.datetime.strptime(fire_start_day, '%Y-%m-%d')
    pre_fire_start_day_dt = fire_start_day_dt - dt.timedelta(days=30)
    pre_fire_start_day = dt.datetime.strftime(pre_fire_start_day_dt, '%Y-%m-%d')
    pre_folder = sentinel_request(area_bbox, pre_fire_start_day, fire_start_day, "pre")

    # Request first image post-fire
    fire_end_day_dt = dt.datetime.strptime(fire_end_day, '%Y-%m-%d')
    post_fire_end_day_dt = fire_end_day_dt + dt.timedelta(days=30)
    post_fire_end_day = dt.datetime.strftime(post_fire_end_day_dt, '%Y-%m-%d')
    post_folder = sentinel_request(area_bbox, fire_end_day, post_fire_end_day, "post")
    
    return pre_folder, post_folder 

def sentinel_request(area_bbox, first_day, last_day, pre_or_post):
    # Create statistical request
    nbr_request = SentinelHubStatistical(
        aggregation=SentinelHubStatistical.aggregation(
            evalscript=nbr_evalscript,
            time_interval=(first_day, last_day),
            aggregation_interval="P1D",
        ),
        input_data=[SentinelHubStatistical.input_data(
            DataCollection.SENTINEL2_L2A, maxcc=0.8)],
        bbox=area_bbox,
        config=config)

    nbr_stats = nbr_request.get_data()[0]
    # transform request to df
    nbr_df = stats_to_df(nbr_stats)
    # Select days mithout clouds
    valid_nbr = nbr_df[nbr_df["nbr_B0_noDataCount"] == 0]
    # Select closest day to fire
    if pre_or_post == "pre":
        day_stats = valid_nbr.iloc[-1]
    elif pre_or_post == "post":
        day_stats = valid_nbr.iloc[0]

    interval_from = dt.datetime.strftime(
        day_stats['interval_from'], '%Y-%m-%d')
    interval_to = dt.datetime.strftime(day_stats['interval_to'], '%Y-%m-%d')

    request_image = SentinelHubRequest(
        data_folder=interval_from,
        evalscript=evalscript_true_color,
        input_data=[SentinelHubRequest.input_data(
            data_collection=DataCollection.SENTINEL2_L2A,
            time_interval=(interval_from, interval_to))],
        responses=[SentinelHubRequest.output_response(
            "default", MimeType.TIFF)],
        bbox=area_bbox,
        config=config)
    imgs = request_image.get_data(save_data=True)
    
    return interval_from

def read_band_image(band, path):
    """
    This function takes as input the Sentinel-2 band name and the path of the
    folder that the images are stored, reads the image and returns the data as
    an array
    input:   band           string            Sentinel-2 band name
             path           string            path of the folder
    output:  data           array (n x m)     array of the band image
             spatialRef     string            projection
             geoTransform   tuple             affine transformation coefficients
             targetprj                        spatial reference
    """
    a = path + '/*/response.tiff'
    img = gdal.Open(glob.glob(a)[0])

    data = np.array(img.GetRasterBand(band).ReadAsArray())
    spatialRef = img.GetProjection()
    geoTransform = img.GetGeoTransform()
    targetprj = osr.SpatialReference(wkt=img.GetProjection())

    return data, spatialRef, geoTransform, targetprj


def nbr(band1, band2):
    """
    This function takes an input the arrays of the bands from the read_band_image
    function and returns the Normalized Burn ratio (NBR)
    input:  band1   array (n x m)      array of first band image e.g B8A
            band2   array (n x m)      array of second band image e.g. B12
    output: nbr     array (n x m)      normalized burn ratio
    """
    nbr = (band1 - band2) / (band1 + band2)
    return nbr


def dnbr(nbr1, nbr2):
    """
    This function takes as input the pre- and post-fire NBR and returns the dNBR
    input:  nbr1     array (n x m)       pre-fire NBR
            nbr2     array (n x m)       post-fire NBR
    output: dnbr     array (n x m)       dNBR
    """
    dnbr = nbr1 - nbr2
    return dnbr


def array2raster(array, geoTransform, projection, filename):
    """
    This function tarnsforms a numpy array to a geotiff projected raster
    input:  array                       array (n x m)   input array
            geoTransform                tuple           affine transformation coefficients
            projection                  string          projection
            filename                    string          output filename
    output: dataset                                     gdal raster dataset
            dataset.GetRasterBand(1)                    band object of dataset

    """
    pixels_x = array.shape[1]
    pixels_y = array.shape[0]

    # mask
    copied_array = copy.copy(array)
    copied_array[array < 0.10] = np.nan
    driver = gdal.GetDriverByName('GTiff')
    dataset = driver.Create(
        filename,
        pixels_x,
        pixels_y,
        1,
        gdal.GDT_Float64, )
    dataset.SetGeoTransform(geoTransform)
    dataset.SetProjection(projection)
    dataset.GetRasterBand(1).WriteArray(copied_array)
    dataset.GetRasterBand(1).SetNoDataValue(np.nan)
    dataset.FlushCache()
    dataset = None


def getFeatures(gdf):
    """Function to parse features from GeoDataFrame in such a manner that rasterio wants them"""
    import json
    return [json.loads(gdf.to_json())['features'][0]['geometry']]


def poligonize(in_raster, out_geojson):
    """
    

    Parameters
    ----------
    in_raster : TYPE
        DESCRIPTION.
    out_geojson : TYPE
        DESCRIPTION.

    Returns
    -------
    polygons : TYPE
        DESCRIPTION.

    """
    with rasterio.open(in_raster) as src:
        src_band = src.read(1)
        src_band = np.float32(src_band)
        src_band[~np.isnan(src_band)] = 1
        shapes = list(rasterio.features.shapes(
            src_band, transform=src.transform))

    shp_schema = {'geometry': 'Polygon', 'properties': {'pixelvalue': 'int'}}

    with fiona.open(out_geojson, 'w', "GeoJSON", shp_schema, crs.to_string(src.crs)) as shp:
        polygons = [shape(geom)for geom, value in shapes if value == 1]
        for pol in polygons:
            shp.write({'geometry': mapping(pol),
                       'properties': {'pixelvalue': int(1)}})

    return polygons


