import pandas as pd
import os
from os import walk
import numpy as np
import requests

print("Running test")

client_id = "testClient"
root_dir = "dataset"
remoteServiceBaseUrl = "http://localhost:21021"

df = pd.read_csv(os.path.join(root_dir, "DATA-mental_health_in_tech.csv"))
def compute_2D_numerical_histogram(df, attribute1, start1, end1, bins1, attribute2, start2, end2, bins2):
    df1 = df[df[attribute1] <= end1]
    df1 = df1[df1[attribute1] >= start1]
    df1 = df1[df1[attribute2] <= end2]
    df1 = df1[df1[attribute2] >= start2].loc[:,[attribute1,attribute2]]
    p = np.histogramdd(df1.values, bins=[np.linspace(start1, end1, num=bins1+1), np.linspace(start2, end2, num=bins2+1)])
    histo = list(p[0].flatten())
    return histo

def compute_2D_categorical_histogram(df, attribute1, values1, attribute2, values2):
    df1 = df[df[attribute1].isin(values1)]
    df1 = df1[df1[attribute2].isin(values2)].loc[:,[attribute1,attribute2]]
    tmp = []
    for k in sorted(values2):
        filtered = df1[df1[attribute2] == k]
        for v in sorted(values1):
            print(k,v)
            tmp.append(filtered[filtered[attribute1] == v].shape[0])
    return tmp

def compute_2D_mixed_histogram(df, attribute1, values1, attribute2, start2, end2, bins2):
    df1 = df[df[attribute1].isin(values1)]
    df1 = df1[df1[attribute2] <= end2]
    df1 = df1[df1[attribute2] >= start2].loc[:,[attribute1,attribute2]]
    df1[attribute1] = df1[attribute1].apply(lambda x: values1.index(x))
    p = np.histogramdd(df1.values, bins=[range(len(values1) + 1), np.linspace(start2, end2, num=bins2+1)])
    return list(p[0].T.flatten())

def compute_categorical_histogram(df, attribute, values):
    df = df[df[attribute].isin(values)][attribute]
    histo = df.value_counts().to_dict()
    tmp = {}
    for k in sorted(values):
        tmp[k] = histo[k] if k in histo else 0
    return tmp

r = compute_categorical_histogram(df, "Country", ["Bulgaria", "Canada", "United States", "United Kingdom", "Netherlands", "Switzerland", "Portugal", "France"])
print(r)
# datasets = next(walk(root_dir), (None, None, []))[2]  # [] if no file

# for dataset in [d for d in datasets if d.startswith("DATA-")]:
#     tmp = {"client_id": client_id, "name": dataset.split(".")[0].split("DATA-")[1]}
#     df = pd.read_csv(os.path.join(root_dir, dataset))
#     tmp["attributes"] = df.columns.tolist()
#     tmp["dtypes"] = {}
#     tmp["values"] = {}
#     for col in df:
#         tmp["dtypes"][col] = str(df[col].dtype)
#         if df[col].dtype == "object":
#             tmp["values"][col] = df[col].unique().tolist()
# try:
#     print("posting")
#     r = requests.post(
#             remoteServiceBaseUrl + "/api/services/app/Dataindex/RegisterData",
#             json=tmp
#         )
#     print(r.status_code)
# except Exception as e:
#     print(e)
