import yaml
import pandas as pd

# paths to files
infile = r"E:\GA\UDF\compilation\staging\UDF_bore_loading.xlsx"


df = pd.read_excel(infile, engine = "openpyxl", sheet_name = 'UDF_LithologyLog')

with open('boreholes\\lithMapping.yaml') as file:

    lithologyMapping = yaml.load(file, Loader=yaml.FullLoader)['lithologyMapping']

df['GALithType'] = [s.lower() for s in df['MajorLithCode'].values]

missing_liths = []
for lith in df['GALithType'].unique():
    found = False
    if lith in lithologyMapping.keys():
        continue
    else:
        mask = df[df['GALithType'] == lith]

        for ltype in lithologyMapping.keys():
            alt_names = lithologyMapping[ltype]
            if lith in alt_names:
                df.at[mask.index, 'GALithType'] = ltype
                found = True
        if not found:
            print(lith)
            df.at[mask.index, 'GALithType'] = "unk"


df.to_csv(r"lithlog_updated.csv")

