import geopandas as gpd
import pandas as pd

infile = r"output\UDF_Boreholes.gpkg"

gdf = gpd.read_file(infile, layer='UDF_Bores').to_crs("epsg:28355")

gdf['X'] = [g.x for g in gdf.geometry]
gdf['Y'] = [g.y for g in gdf.geometry]

df_export = gdf[['HydroCode', 'HydroID', 'X', 'Y', 'GALandElev', 'DrilledDepth']]


mask = pd.isnull(df_export.HydroCode)

missing_names = gdf[mask]['BoreName'].values

df_export.at[df_export[mask].index, "HydroCode"] = missing_names

df_export.fillna(0).to_csv(r"output\UDF_headers.txt", sep = "\t", index = False)

# now export the well tops

gdf_bl = gpd.read_file(infile, layer='UDF_BoreLog')

# join to get the coordinates

df_bl_export = gdf_bl.merge(gdf[['HydroID', 'X', 'Y']], left_on="BoreID", right_on="HydroID")[['BoreID', 'HydroCode', 'FromDepth', 'GA_UNIT', "X", "Y", "TopElev"]]

mask = pd.notnull(df_bl_export.GA_UNIT)

# export
df_bl_export[mask].to_csv(r"output\UDF_formation_top.txt", sep = "\t", index = False)

# now we export lithlogs


gdf_ll = gpd.read_file(infile, layer='UDF_LithologyLog')

df_ll_export = gdf_ll.merge(gdf[['HydroID', 'X', 'Y']], left_on="BoreID", right_on="HydroID")[['BoreID', 'HydroCode', 'FromDepth', "ToDepth", 'GALithType', 'MajorLithCode', 'MinorLithCode', 'Description', "X", "Y", "TopElev"]]

df_ll_export.fillna("", inplace=True)

# export
df_ll_export.to_csv(r"output\UDF_lithlog.txt", sep = "\t", index = False)

