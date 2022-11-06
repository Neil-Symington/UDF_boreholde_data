import os
import pandas as pd
import numpy as np
import sys
sys.path.append(r'H:\scripts')
import connect_to_oracle
from pyproj import Transformer
import geopandas as gpd

# Open our spreadsheet

borefile = r"MORPH_bore_NGIS_extraction.csv"

#gdf = pd.read_csv(borefile)

# Set up a connection to the oracle database
ora_con = connect_to_oracle.connect_to_oracle()


# Create a sql query

header_query = """

SELECT  b.borehole_name, b.borehole_id, b.location, sum.*
  FROM  borehole.boreholes b
        left join BOREHOLE.ALL_BOREHOLE_CURRENT_SUMMARY sum on b.borehole_id = sum.eno
  WHERE SDO_INSIDE(b.location,
            SDO_GEOMETRY(2003, 3577, NULL,
              SDO_ELEM_INFO_ARRAY(1,1003,1),
              SDO_ORDINATE_ARRAY(1017760.76728096301667392, -3541957.70058736298233271,
                                 1033044.96912370761856437, -3380500.8970661829225719,
                                  1362219.94902850710786879, -3210531.94267989695072174,
                                   1461582.75826686783693731, -3229754.48591392068192363,
                                    1547489.18534193048253655, -3368580.82105459086596966,
                                     1518569.3516713276039809, -3414031.0364407654851675,
                                      1418155.4332151913549751, -3421778.12315146625041962,
                                       1359002.49710371834225953, -3370541.71342544769868255,
                                        1317053.06696818908676505, -3416099.50407753139734268,
                                         1073812.87129989336244762, -3543764.89405762869864702,
                                          1017760.76728096301667392, -3541957.70058736298233271))
            ) = 'TRUE'
"""

df_header = pd.read_sql_query(header_query, con = ora_con)

# save the header to disc

df_header.to_csv(r"E:\GA\UDF\compilation\staging", index=False)