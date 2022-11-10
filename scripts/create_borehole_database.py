import geopandas as gpd
import pandas as pd
import shapely
from pyproj import Transformer
import numpy as np
from shapely.geometry import Point
import rasterio
import matplotlib.pyplot as plt
from collections import OrderedDict
import glob, os


def transform_coords(x,y,inProj, outProj):
    transformer = Transformer.from_crs(inProj, outProj, always_xy = True)
    return transformer.transform(x,y)

def find_zone(lon):
    if lon > 150.:
        return 55
    else:
        return 54

def check_table_validity(df, gdf):
    # check table validity, add more checks as they come to mind
    assert np.all(np.isin(df['BoreID'].values, gdf['HydroID'].values))

def load_and_process_table(infile):
    print(infile)
    # adjust each hole so it is relative to groundlevel
    df  = pd.read_csv(infile)

    df = df.merge(gdf[['HydroID', 'HydroCode','RefElev', 'RefElevDesc', 'GALandElev', 'geometry']],
                  left_on=['BoreID', 'HydroCode'], right_on = ['HydroID', 'HydroCode'],
                                        suffixes=('_borelog', '_collar'))
    # remove duplicate rows
    df = df.drop_duplicates()

    df['offset'] = df['RefElev_collar'] - df['GALandElev']

    for index, row in df.iterrows():
        if row.RefElevDesc_borelog == "NGS":
            continue
        elif row.RefElevDesc_borelog in ['COV', 'FLN', 'TOC', 'UNK']:
            df.at[index, 'FromDepth'] = row.FromDepth - row.offset
            df.at[index, 'ToDepth'] = row.ToDepth - row.offset
        else:
            print(row)
            print("Please fill in the reference elevation for bore {}".format(row.HydroCode))
    df['FromDepth'] = df['FromDepth'].round(2)
    df['FromDepth'] = df['FromDepth'].round(2)

    #now update the elevation from and to columns
    df['TopElev'] = (df['GALandElev'] - df['FromDepth']).round(2)
    df['BottomElev'] = (df['GALandElev'] - df['ToDepth']).round(2)

    check_table_validity(df, gdf)

    # convert to a geodataframe so it can load into a geopackage
    new_gdf = gpd.GeoDataFrame(df, geometry='geometry',crs = "EPSG:3577")

    new_gdf["geometry"] = [None for i in new_gdf.index]

    return new_gdf


# paths to files
infile = r"..\staging_data\UDF_Bore_staging.csv"

dem_path = r"E:\GA\UDF\data\elevation\UDF_DEM_gda94.tif"

df = pd.read_csv(infile)

# drop any creepy nan rows
df.dropna(how='all', inplace=True)

# Now we have to deal with non-unique identifiers

df = df.sort_values(by=['HydroID'])

assert len(df['HydroID']) == len(df['HydroID'].unique())

# we need to complete the geometry column and all coordinate columns

for index, row in df.iterrows():
    x,y = row['Easting'], row['Northing']
    lon, lat = row['Longitude'], row['Latitude']
    geom = row['geometry']
    # if all are nulls raise an error
    if np.all(pd.isnull([x,y,lon,lat])):
        print("Row {} is missing coordinate information".format(index))
        break
    # get the projection zone
    zone = row['ProjectionZone']
    if pd.isnull(zone):
        zone = find_zone(lon)
        df.at[index, 'ProjectionZone'] = zone
    if not pd.isnull(geom):
        # if not a string convert to point object
        if isinstance(row['geometry'],str):
            df.at[index, 'geometry'] = shapely.wkt.loads(row['geometry'])
    # if the geometry object doesn't exist, create it
    else:
        if not np.any(np.isnan([lon,lat])):
            newx,newy = transform_coords(lon,lat, "EPSG:4283","EPSG:3577")
        else:
            newx,newy = transform_coords(x,y, "EPSG:283{}".format(zone),"EPSG:3577")
        df.at[index, 'geometry'] = Point(newx, newy)
        
    # now add the other coords if they are not present
    if np.any(np.isnan([x,y])):
        newx,newy = transform_coords(lon,lat, "EPSG:4283","EPSG:283{}".format(zone))
        df.at[index, 'Easting'] = newx
        df.at[index, 'Northing'] = newy
    if np.any(np.isnan([lon,lat])):
        newlon,newlat = transform_coords(x,y,"EPSG:283{}".format(zone),  "EPSG:4283")
        df.at[index, 'Longitude'] = newlon
        df.at[index, 'Latitude'] = newlat

gdf = gpd.GeoDataFrame(df, geometry='geometry',crs = 'EPSG:3577')

#gdf['BoreName'] = ''

#gdf_gda = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(gdf.Longitude, gdf.Latitude),crs = 'EPSG:4283')

# Plot the two sets of points to ensure they are in the same location
check_plot = False

if check_plot:

    fig, (ax1) = plt.subplots(1,1)
    gdf.plot(ax = ax1, c = 'blue', markersize = 8, label = "Albers")
    gdf_gda.plot(ax = ax1, c = 'red', markersize = 1, label = "GDA95")
    ax1.legend()
    plt.show()


# now lets sample the srtm for the NGIS

src = rasterio.open(dem_path)
elevs = [v[0] for v in src.sample(gdf[['Longitude','Latitude']].values)]

gdf['DEM'] = elevs

# add routine for picking our GA prefered elevation do a bunch of logical checks

gdf['GALandElev'] = np.nan
gdf['GALandElevMethod'] = ''

for index, row in gdf.iterrows():
    if np.isnan(row.RefElev) and np.isnan(row.LandElev):
        gdf.at[index, 'GALandElev'] = np.round(row.DEM, 0)
        gdf.at[index, 'GALandElevMethod'] = 'DEM'
    elif row.RefElevMethod in ['UNK', 'EST', 'DEM', 'SAT', 'GPS', 'MAP'] and row.LandElevMethod in ['UNK', 'EST', 'DEM', "SAT", 'GPS', 'MAP']:
        gdf.at[index, 'GALandElev'] = row.DEM
        gdf.at[index, 'GALandElevMethod'] = 'DEM'
    elif row.LandElevMethod in ['SVY', 'GDF', 'LIDAR']: #GPS locations take precedent
        gdf.at[index, 'GALandElev'] = np.round(row.LandElev,2)
        gdf.at[index, 'GALandElevMethod'] = row.LandElevMethod
    elif row.RefElevDesc == 'NGS' and row.RefElevMethod in ['SVY', 'GDF']:
        gdf.at[index, 'GALandElev'] = np.round(row.RefElev,2)
        gdf.at[index, 'GALandElevMethod'] = row.RefElevMethod
    else:
        print(row)
        break

# Now we go about estimating our reference elevation
for index, row in gdf.iterrows():
    offset = row.RefElev - row.LandElev
    if row.RefElevDesc == 'NGS' or pd.isnull(offset):
        gdf.at[index, 'RefElev'] = row.GALandElev
        gdf.at[index, 'RefElevMethod'] = row.GALandElevMethod
    elif row.RefElevDesc in ['TOC', 'COV',  'FLN']:
        gdf.at[index, 'RefElev'] = row.GALandElev + offset
    elif row.RefElevDesc == 'UNK':
        # preserve the offset if it is sensible as it may be real
        
        if np.isclose(offset, 0):
            gdf.at[index, 'RefElev'] = row.GALandElev
            gdf.at[index, 'RefElevMethod'] = row.GALandElevMethod
            gdf.at[index, "RefElevDesc"] = "NGS"
        elif np.abs(offset) < 6.:
            gdf.at[index, 'RefElev'] = row.GALandElev + offset
            gdf.at[index, 'RefElevMethod'] = row.GALandElevMethod
        else:
            gdf.at[index, 'RefElev'] = row.GALandElev
            gdf.at[index, 'RefElevMethod'] = row.GALandElevMethod
            gdf.at[index, "RefElevDesc"] = "NGS"

    else:
        print(row)
        break

# now we search for hydrochem
#chemFile = r"C:\Users\u77932\Documents\UDF\data\boreholes\compilation\additional_tables\UDF_Hydrochem_all data 31_03_22.xlsx"
#df_chem = pd.read_excel(chemFile, sheet_name = 'Compilation', engine = "openpyxl", )

#gdf['HydroChem'] = 0

#chemMask = gdf['HydroCode'].isin(df_chem['BoreID'])
#gdf.at[gdf[chemMask].index, 'HydroChem'] = 1


# iterate through each row and pick the best 

schema = {'properties': OrderedDict([('BoreName', 'str:200'), ('HydroID', 'int'), ('HydroCode', 'str:30'), ('StateBoreID', 'str:50'),
         ('StatePipeID', 'str:30'), ('StateTerritory', 'str:6'), ('Agency', 'int'), ('WCode', 'int'), ('BoreDepth', 'float'), ('DrilledDepth', 'float'),
         ('Status', 'str:30'), ('DrilledDate', 'datetime'), ('HGUID', 'int'), ('HGUNumber', 'int'), ('HGUName', 'str:200'), ('NafHGUNumber', 'int'),
          ('AquiferType', 'int'), ('FType', 'str:50'), ('Latitude', 'float'), ('Longitude', 'float'), ('Easting', 'float'), ('Northing', 'float'),
          ('Projection', 'int'), ('ProjectionZone', 'int'), ('CoordMethod', 'str:30'), ('HeightDatum', 'str:30'), ('GALandElev', 'float'), ('GALandElevMethod', 'str:30'),
          ('RefElev', 'float'), ('RefElevDesc', 'str:30'), ('RefElevMethod', 'str:30'),
         ('FTypeClass', 'str:50'), ('ConstructionLog', 'int'), ('LithLog', 'int'), ('HydrostratLog', 'int'),
          ('WaterLevel', 'int'), ('Salinity', 'int'),
          ('AddedBy', 'str:20'), ('Comment', 'str:100'), ('Source', 'str:20'), ("QAQCd_By", 'str:20'), ('QAQC_date', 'date')]),
           'geometry': 'Point'}

cols = [c for c in schema['properties']] + ['geometry']

UDF_file = r"..\output\UDF_Boreholes.gpkg"

# now export csv

gdf[cols].to_csv(r"..\output\UDF_Bore.csv", index = False)

gdf[cols].to_file(UDF_file, layer='UDF_Bores', driver="GPKG", schema = schema)
#gdf[cols].to_file("UDF_Boreholes.gdf", driver="FileGDB", schema = schema)

# Now bring in the other tables
borelog_file = r"..\staging_data\UDF_BoreLog_staging.csv"

gdf_borelogs = load_and_process_table(borelog_file)

bl_schema = {'properties': OrderedDict([('BoreID', 'int'), ('HydroCode', 'str:30'), ('FromDepth', 'float'), ('ToDepth', 'float'),
                                       ('TopElev', 'float'), ('BottomElev', 'float'), ('HGUID', 'int'),
                                        ('HGUNumber', 'int'), ('NafHGUNumber', 'int'), 
                                        ('NafHGUName', 'str:255'), ('Description', 'str:255'), 
                                        ('Author', 'str:50'), ('Source', 'str:100'), ('Comment', 'str:250'),
                                        ('GA_UNIT', 'str:30'), ('GA_STRATNO', 'int')
                                        ]), 'geometry': 'None'}

bl_cols = [c for c in bl_schema['properties']] + ['geometry']
gdf_borelogs[bl_cols].to_file(UDF_file, layer='UDF_Borelog', driver="GPKG", schema = bl_schema)

gdf_borelogs[bl_cols].to_csv(r"..\output\UDF_BoreLog.csv", index = False)

# To write to a geopackage, the dataframe needs to first be written as a geodataframe

lithlog_file = r"..\staging_data\UDF_LithLog_staging.csv"

gdf_lithlog = load_and_process_table(lithlog_file)

ll_schema = {'properties': OrderedDict([('BoreID', 'int'), ('HydroCode', 'str:30'), ('FromDepth', 'float'), ('ToDepth', 'float'),
                                        ('TopElev', 'float'), ('BottomElev', 'float'), ('GALithType', 'str:50'), ('MajorLithCode', 'str:50'),
                                        ('MinorLithCode', 'str:50'), ('Description', 'str:255'), ('Source', 'str:100'),
                                        ('LogType', 'int')
                                        ]), 'geometry': 'None'}

ll_cols = [c for c in ll_schema['properties']] + ['geometry']
gdf_lithlog[ll_cols].to_file(UDF_file, layer='UDF_LithologyLog', driver="GPKG", schema = ll_schema)

gdf_lithlog[ll_cols].to_csv(r"..\output\UDF_LithLog.csv", index = False)

constructionlog_file = r"..\staging_data\UDF_ConstructionLog_staging.csv"
gdf_constrlog = load_and_process_table(constructionlog_file)


cl_schema = {'properties': OrderedDict([('BoreID', 'int'), ('HydroCode', 'str:30'), ('FromDepth', 'float'), ('ToDepth', 'float'),
                                        ('TopElev', 'float'), ('BottomElev', 'float'),
                                        ('ConstructionType', 'str:50'), ('Material', 'str:50'), ('InnerDiameter', 'float'),
                                         ('OuterDiameter', 'float'), ('Property', 'str:50'), ('PropertySize', 'float'), ('DrillMethod', 'str:50'), ('LogType', 'int')
                                        ]), 'geometry': 'None'}

cl_cols = [c for c in cl_schema['properties']] + ['geometry']

gdf_constrlog[cl_cols].to_csv(r"..\output\UDF_ConstructionLog.csv", index = False)

gdf_constrlog[cl_cols].to_file(UDF_file, layer='UDF_ConstructionLog', driver="GPKG", schema = cl_schema)

# now we add the conductivity data

indir = r"E:\GA\UDF\data\AEM\UDF_release\03_LCI\03_LCI\03_Depth_Slices\Grids_doi_Masked"

gdf_cond = gdf[['HydroID', 'geometry']].to_crs("epsg:7855")


easting = [g.x for g in gdf_cond.geometry]
northing = [g.y for g in gdf_cond.geometry]
coords = np.column_stack((easting, northing))

fnames = glob.glob(os.path.join(indir,'*.ers'))

for i in range(1,31):
    layer = "Con" + str(i).zfill(3)
    file = list(filter(lambda x: layer in x, fnames))[0]
    src = rasterio.open(file)
    cond = np.nan * np.ones(shape = len(gdf_cond), dtype = float)
    for j in range(len(cond)):
        try:
            cond[j] = next(src.sample(np.expand_dims(coords[j], axis=0)))[0] * 10**-3
        except IndexError:
            pass
    cond[cond == -999.999] = np.nan
    gdf_cond[layer] = cond

gdf_cond_ss = gdf_cond[np.isfinite(gdf_cond['Con001'])]

cond_schema = {'properties': OrderedDict([('BoreID', 'int')]), 'geometry': 'None'}

for i in range(1,31):
    layer = "Con" + str(i).zfill(3)
    cond_schema['properties'][layer] = 'float'

cond_cols = [c for c in cond_schema['properties']] + ['geometry']

gdf_cond_ss.rename(columns = {'HydroID':"BoreID"}, inplace = True)

gdf_cond_ss["geometry"] = [None for i in gdf_cond_ss.index]

gdf_cond_ss[cond_cols].to_file(UDF_file, layer='UDF_Conductivity', driver="GPKG", schema = cond_schema)

