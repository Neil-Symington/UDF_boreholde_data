import geopandas as gpd
import pandas as pd
import rasterio
import os
from shapely.geometry import Polygon
from shapely import wkt
import gc
import numpy as np
import math

def extractNGIStables(geopackage_path, layer_name, uid_col):

    # Now lets extract data from borehole log table

    gdf_table = gpd.read_file(geopackage_path, layer = layer_name, driver='FileGDB')

    # filter this based on our hydroid

    mask = gdf_table[uid_col].isin(gdf_UDF['HydroID'])

    gdf_UDF_table = gdf_table[mask]

    # Gtt the UDF_ID column

    gdf_UDF_table = gdf_UDF_table.merge(gdf_UDF[['HydroID', "UDF_ID"]], left_on = uid_col, right_on =  'HydroID')

    gdf_UDF_table.drop(columns = ['HydroID'], inplace = True)

    return gdf_UDF_table

# Use wkt to describe a polygon (in Australia albers (3577)) for clipping our NGIS data

bounding_box = "Polygon ((1017760.76728096301667392 -3541957.70058736298233271, 1033044.96912370761856437 -3380500.8970661829225719, 1362219.94902850710786879 -3210531.94267989695072174, 1461582.75826686783693731 -3229754.48591392068192363, 1547489.18534193048253655 -3368580.82105459086596966, 1518569.3516713276039809 -3414031.0364407654851675, 1418155.4332151913549751 -3421778.12315146625041962, 1359002.49710371834225953 -3370541.71342544769868255, 1317053.06696818908676505 -3416099.50407753139734268, 1073812.87129989336244762 -3543764.89405762869864702, 1017760.76728096301667392 -3541957.70058736298233271))"

p1 = wkt.loads(bounding_box)

ngis_gpkg = r"C:\Users\u77932\Documents\NGS\data\NGIS\NGIS_v1.7.gpkg"

ngis_gdb = r"E:\GA\NGIS\NGIS_v1pt7pt0.gdb"


# get the NGIS entries that are within our bounding box
#gdf = gpd.read_file(ngis_gpkg, layer = 'NGIS_v1pt7pt0 NGIS_Bore')

gdf = gpd.read_file(ngis_gdb, driver='FileGDB', layer='NGIS_Bore')

gdf_UDF = gdf[gdf.geometry.within(p1)]

gdf = None
gc.collect()


gdf_UDF['AddedBy'] = "Neil Symington"
gdf_UDF['Comment'] = ""
gdf_UDF['SOURCE'] = "NGIS"

# drop some less relevent columns
cols2drop = ['BoreLineCode', 'WorksID', 'LicenceExtractID','LicenceExtractVolume', 'LicenceUseID',
             'WaterCount', 'WaterDateMin', 'WaterDateMax', 'SalinityCount', 'SalinityDateMin',
             'SalinityDateMax', 'BoreLineCode']
            
gdf_UDF.drop(columns = cols2drop, inplace=True)

# Now export the data as a spreadsheet
gdf_UDF.to_csv("UDF_bore_NGIS_extraction.csv", index=False)

# Extract borehole log data

gdf_UDF_bl = extractNGIStables(ngis_gdb, 'NGIS_BoreholeLog', 'BoreID')

# drop nulls

gdf_UDF_bl = gdf_UDF_bl[gdf_UDF_bl['HGUID'] != -79999999]

# join this onto the hydrostratigraphic unit name

gdf_hgu = gpd.read_file(ngis_gdb, layer = "NGIS_HydrogeologicUnit")

gdf_UDF_bl = gdf_UDF_bl.merge(gdf_hgu[['HydroID', 'NafHGUName']], left_on = 'HGUID', right_on =  'HydroID', how="left")

# Add columns
gdf_UDF_bl['GA_UNIT'] = ""

gdf_UDF_bl['GA_STRATNO'] = -999999

gdf_UDF_bl['Comment'] = ""

gdf_UDF_bl.to_csv('UDF_boreholelogs.csv', index=False)

# Now lets extract data from construction log table

gdf_constructionlog = extractNGIStables(ngis_gdb, 'NGIS_ConstructionLog', 'BoreID')

gdf_constructionlog.to_csv('UDF_constructionlogs.csv', index=False)

# Now lets extract data from lithology logs

gdf_lithlogs = extractNGIStables(ngis_gdb, 'NGIS_LithologyLog', 'BoreID')

gdf_lithlogs.to_csv('UDF_lithologylogs.csv', index=False)
