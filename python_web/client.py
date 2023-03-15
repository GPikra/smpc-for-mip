from cmath import log
import csv
import traceback
from flask import Flask, jsonify, request
from time import sleep
from flask_cors.extension import CORS
from flask_restful import Resource, Api, abort
import subprocess
import json
import argparse
import numpy as np
from threading import Thread
import requests
import os
import shutil
from logistic_regressor import model_optimize
from auxfiles.customLogger import Logger
from auxfiles.appconsts import *
from os import walk
import pandas as pd
logger = Logger(['root', 'client'])
logger.info("Client Initialized.")

# parser = argparse.ArgumentParser(description='Process some integers.')
# parser.add_argument(
#     'client_id',
#     metavar='id',
#     type=int,
#     nargs=1,
#     help='Specify client Id'
# )

# args = parser.parse_args()
# client_id = args.client_id[0]
PRECISION = 1e9
client_id = os.environ["ID"]
# log client id
logger.info("Client ID: {0}".format(client_id))

app = Flask(__name__)
api = Api(app)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# def mip_task_data(x): return "dataset/mip_task_{1}_{0}.txt".format(x, client_id)
dataset = "dataset/dataset.txt"
json_dataset = "dataset/full_dataset_{0}.json".format(client_id)
def job_dataset(x): return "dataset/dataset_{1}_{0}.txt".format(x, client_id)
# coordinator = "http://0.0.0.0:12314/api/register-client"

remoteServiceBaseUrl = os.environ[REMOTE_SERVICE_URL] if REMOTE_SERVICE_URL in os.environ else None
player2_url = os.environ[PLAYER_REPO_2].split("http://")[1].split(":")[0]
player1_url = os.environ[PLAYER_REPO_1].split("http://")[1].split(":")[0]
player0_url = os.environ[PLAYER_REPO_0].split("http://")[1].split(":")[0]

networkData = os.path.join(os.getcwd(), "Data", "NetworkData.txt")

with open(networkData, 'w') as f:
    f.write(
        "RootCA.crt\n3\n0 {0} Player0.crt P0\n1 {1} Player1.crt P1\n2 {2} Player2.crt P2\n0\n0".format(
            player0_url, player1_url, player2_url
        )
    )

if remoteServiceBaseUrl is not None:
    root_dir = "dataset"

    datasets = next(walk(root_dir), (None, None, []))[2]  # [] if no file
    logger.info("Datasets: {0}".format([d for d in datasets if d.startswith("DATA-")]))
    for dataset in [d for d in datasets if d.startswith("DATA-")]:
        tmp = {"client_id": client_id, "name": dataset.split(".")[0].split("DATA-")[1]}
        df = pd.read_csv(os.path.join(root_dir, dataset))
        tmp["attributes"] = df.columns.tolist()
        tmp["dtypes"] = {}
        tmp["values"] = {}
        for col in df:
            tmp["dtypes"][col] = str(df[col].dtype)
            if df[col].dtype == "object":
                tmp["values"][col] = df[col].unique().tolist()
        r = requests.post(
                remoteServiceBaseUrl + "/api/services/app/Dataindex/RegisterData",
                json=tmp
            )
        while r.status_code != 200:
            r = requests.post(
                remoteServiceBaseUrl + "/api/services/app/Dataindex/RegisterData",
                json=tmp
            )
            logger.info(r.__dict__)
        logger.info("sent: {0}, {1}".format(r.status_code, dataset))

coordinator = os.environ[COORDINATOR_URL]
dest_crt = os.path.join(os.getcwd(), "Cert-Store",
                        "Client{0}.crt".format(client_id))
dest_key = os.path.join(os.getcwd(), "Cert-Store",
                        "Client{0}.key".format(client_id))
dest_csr = os.path.join(os.getcwd(), "Cert-Store",
                        "Client{0}.csr".format(client_id))


def generate_cert_files():
    logger.info("Certs Exist. Skipping generation...")
    if not os.path.exists(dest_crt) or not os.path.exists(dest_key):
        logger.info("New Certs generated")
        out = subprocess.check_output(
            [
                "./gen_client_certificate.sh",
                "-n",
                str(client_id),
                "-c",
                "Cert-Store/RootCA.crt",
                "-k",
                "Cert-Store/RootCA.key",
                "-d",
                str(client_id)
            ])
        logger.info(out)
        shutil.move(
            os.path.join(os.getcwd(), "Client{0}.crt".format(client_id)), dest_crt)
        shutil.move(
            os.path.join(os.getcwd(), "Client{0}.key".format(client_id)), dest_key)
        shutil.move(
            os.path.join(os.getcwd(), "Client{0}.csr".format(client_id)), dest_csr)


def find_coordinator():
    try:
        try:
            generate_cert_files()
            with open(dest_crt, "r") as f:
                text = f.read()  # "".join(f.read().splitlines())

            r = requests.post(
                coordinator + "/api/register-client",
                json={
                    "force": True,
                    "client_id": client_id,
                    "port": int(os.environ[PORT]),
                    "crt": text
                }
            )
            if r.status_code != 200:
                logger.info(
                    "Error registering with coordinator: {0}".format(r.text))
                raise Exception(
                    "Error registering with coordinator: {0}".format(r.text))
            logger.info("Connected to coordinator.")
        except requests.ConnectionError:
            logger.error("Error connecting to coordinator.")
            raise Exception("Error connecting to coordinator.")
    except Exception:
        logger.error(
            traceback.format_exc()
        )
        logger.warning("Failed to find coordinator. At {0}".format(
            coordinator + "/api/register-client"))
        sleep(5)
        find_coordinator()
        return 0


thread = Thread(target=find_coordinator, args=())
thread.start()


class TriggerImportation(Resource):
    def get(self, jobId):
        logger.info("Importation trigger request received.")
        cmd_run_clients = "./Client-Api.x {0} {1}".format(
            client_id, job_dataset(jobId))
        cmdpipe = subprocess.Popen(
            cmd_run_clients, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        logger.info("The commandline is {}".format(cmd_run_clients))
        while True:
            out = cmdpipe.stdout.readline().decode()
            if out == "":
                break
            logger.info("[IMPORTER LOGS] {0}".format(out))


class GetDatasetSize(Resource):
    def get(self, jobId):
        logger.info(
            "Received request for dataset size for jobId {0}.".format(jobId))
        if not os.path.exists(job_dataset(jobId)):
            logger.error(
                "Data for jobId {0} is not available. Aborting...".format(jobId))
            abort(400)
        with open(job_dataset(jobId), 'r') as f:
            lines = f.readlines()
            logger.info("Found {1} datapoints for jobId {0}.".format(
                jobId, len(lines)))
            return len(lines)


class ChangeData(Resource):
    def get(self, jobId):
        logger.info(
            "Received request for dataset report for jobId {0}.".format(jobId))
        if os.path.exists(job_dataset(jobId)):
            with open(job_dataset(jobId), 'r') as f:
                ret = [int(i.split("\n")[0]) for i in f.readlines()]
                return jsonify(ret)
        else:
            logger.warning("No dataset found for jobId {0}.".format(jobId))
            return '', 204

    def post(self, jobId):
        logger.info(
            "Received request for dataset creation/update for jobId {0}.".format(jobId))
        json_data = request.get_json(force=True)
        try:
            if json_data["type"] == "int":
                with open(job_dataset(jobId), 'w') as f:
                    try:
                        f.writelines(
                            [str(int(i)) + '\n' for i in json_data["data"]])
                        logger.info(
                            "Dataset created/updated for jobId {0}. {1}".format(jobId, [str(int(i)) + '\n' for i in json_data["data"]]))
                    except ValueError:
                        logger.error(
                            "Bad data format")
                        abort(400)
            else:
                with open(job_dataset(jobId), 'w') as f:
                    tmp = []
                    for i in json_data["data"]:
                        tmp.append(str(int(i)) + "\n")
                        tmp.append(
                            str(int((float(i) - int(i)) * PRECISION)) + "\n")
                    f.writelines(tmp)
                    logger.info(
                        "Dataset created/updated for jobId {0}. {1}".format(jobId, tmp))
        except Exception:
            logger.error(
                "An unexpected error occurred when attemptin to write data. Aborting... {0}".format(traceback.format_exc()))
            abort(500)
        return '', 200

def compute_numerical_histogram(df, attribute, start, end, bins):
    df = df[df[attribute] <= end]
    df = df[df[attribute] >= start][attribute]
    p = np.histogram(df, bins=np.linspace(start, end, num=bins+1))
    histo = list(p[0])
    if len(histo) > bins:
        histo[-2] += histo[-1]
        return histo[:-1]
    return histo

def compute_categorical_histogram(df, attribute, values):
    df = df[df[attribute].isin(values)][attribute]
    histo = df.value_counts().to_dict()
    tmp = {}
    for k in sorted(values):
        tmp[k] = histo[k] if k in histo else 0
    return tmp

def compute_2D_numerical_histogram(df, attribute1, start1, end1, bins1, attribute2, start2, end2, bins2):
    df1 = df[df[attribute1] <= end1]
    df1 = df1[df1[attribute1] >= start1]
    df1 = df1[df1[attribute2] <= end2]
    df1 = df1[df1[attribute2] >= start2].loc[:,[attribute1,attribute2]]
    p = np.histogramdd(df1.values, bins=[np.linspace(start1, end1, num=bins1+1), np.linspace(start2, end2, num=bins2+1)])
    histo = list(p[0].T.flatten())
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


class MapOperation(Resource):
    def post(self):
        logger.info(
            "Received map operation.")
        json_data = request.get_json(force=True)
        logger.info("Dataset: {0}".format(json_data["DatasetName"]))
        df = pd.read_csv(os.path.join(root_dir, "DATA-" + json_data["DatasetName"] + ".csv"))
        histo = []
        if json_data["MapOperation"] == "histogram":
            if json_data["Bins"] is not None and json_data["Start"] is not None and json_data["Stop"] is not None:
                histo = compute_numerical_histogram(df, json_data["Attribute"], json_data["Start"], json_data["Stop"], json_data["Bins"])                
            else:
                histo = compute_categorical_histogram(df, json_data["Attribute"], json_data["Values"])
                histo = [histo[k] for k in sorted(histo.keys())]
        if json_data["MapOperation"] == "heatmap2DNum":
            logger.info("Map: {0}".format("heatmap2DNum"))
            histo = compute_2D_numerical_histogram(df, json_data["Attribute1"], json_data["Start1"], json_data["Stop1"], json_data["Bins1"], json_data["Attribute2"], json_data["Start2"], json_data["Stop2"], json_data["Bins2"])
        if json_data["MapOperation"] == "heatmap2DCat":
            logger.info("Map: {0}".format("heatmap2DCat"))
            logger.info("Input: {0}".format(json_data))
            histo = compute_2D_categorical_histogram(df, json_data["Attribute1"], json_data["Values1"], json_data["Attribute2"], json_data["Values2"])
        if json_data["MapOperation"] == "heatmap2DMixed":
            logger.info("Map: {0}".format("heatmap2DMixed"))
            logger.info("Input: {0}".format(json_data))
            histo = compute_2D_mixed_histogram(df, json_data["Attribute1"], json_data["Values1"], json_data["Attribute2"], json_data["Start2"], json_data["Stop2"], json_data["Bins2"])
        
        logger.info("Computed Histo: {0}".format(histo))
        with open(job_dataset(json_data["JobId"]), 'w') as f:
            try:
                f.writelines(
                    [str(int(i)) + '\n' for i in histo])
                logger.info(
                    "Dataset created/updated for jobId {0}. {1}".format(json_data["JobId"], [str(int(i)) + '\n' for i in histo]))
            except ValueError:
                logger.error(
                    "Bad data format")
                abort(400)
      

        logger.info("Sending completion notice.")
        try:
            r = requests.get(
                    remoteServiceBaseUrl + "/api/services/app/Smpc/MapOperationCompletion?clientId={0}&jobId={1}".format(client_id, json_data["JobId"]))
            r.raise_for_status()
        except Exception:
            logger.error(
                "An unexpected error occurred when attempting to notify completion. Aborting... {0}".format(traceback.format_exc()))                        
            # while r.status_code != 200:
            #     try:
            #         r = requests.get(
            #                 remoteServiceBaseUrl + "/api/services/app/Smpc/MapOperationCompletion?clientId={0}&jobId={1}".format(client_id, json_data["JobId"]))
            #         r.raise_for_status()
            #     except Exception:
            #         logger.error(
            #             "An unexpected error occurred when attempting to notify completion. Aborting... {0}".format(traceback.format_exc()))
        return '', 200

    
class OpenRStudioServer(Resource):
    def get(self):
        return 'called', 200
    def post(self):
        logger.info(
            "Received OpenRStudioServer operation.")
        json_data = request.get_json(force=True)
        logger.info("Dataset: {0}".format(json_data["DatasetName"]))
        logger.info("JobId: {0}".format(json_data["JobId"]))
        logger.info("Attributes: {0}".format(json_data["Attributes"]))

        root_dir = "dataset"

        if os.path.exists(os.path.join(root_dir, "DATA-" + json_data["DatasetName"] + ".csv")):
            df = pd.read_csv(os.path.join(root_dir, "DATA-" + json_data["DatasetName"] + ".csv"))
            rstudioServerUrl = os.environ['RSTUDIO_SERVER_URL']
            logger.info("rstudioServerUrl: {0}".format(rstudioServerUrl))
            if(json_data["Attributes"] is not None):
                df = df[json_data["Attributes"]]

            try:
                data = {
                    "jobId": json_data["JobId"],
                    "dataset": df.to_json()
                }

                r = requests.post(
                        rstudioServerUrl + "/api/get-dataset", json=data) 

                r.raise_for_status()
            except Exception:
                logger.error(
                    "An unexpected error occurred when attempting to notify completion. Aborting... {0}".format(traceback.format_exc()))                        
                abort(400)
        
        return 'Dataset sent', 200


class DataStandardization(Resource):
    def get(self):
        return 'called', 200
    def post(self):
        
        # get the data from the request body
        json_data = request.get_json(force=True) 

        logger.info("Dataset: {0}".format(json_data["datasetName"]))
        logger.info("newDataset: {0}".format(json_data["newDatasetName"]))
        logger.info("mappedAttributes: {0}".format(json_data["mappedAttributes"]))
        logger.info("mappedValues: {0}".format(json_data["mappedValues"]))

        root_dir = "dataset"

        # Read dataset and save it in a dataframe
        df = pd.read_csv(os.path.join(root_dir, "DATA-"+json_data["datasetName"]+'.csv'))

        # Iterate through mappedValues array and replace values
        for obj in json_data["mappedValues"]:
            for k, v in obj.items():
                logger.info(k)
                if k in df.columns:
                    for key, val in v.items():
                        # replace rows values with mapped values
                        df.loc[df[k] == key, k] = val

        # Iterate through mappedAttributes array and change the column names
        for obj in json_data["mappedAttributes"]:
            for k, v in obj.items():
                # Check if column exists
                if k in df.columns:
                    df.rename(columns = {k:v}, inplace = True)

        # Save new dataset to csv file in dataset folder
        dataset_path = os.path.abspath(os.path.join(__file__ ,'..', root_dir + '/' + "DATA-"+json_data["newDatasetName"]+'.csv'))
        df.to_csv(dataset_path,index=False)
                
        return "OK", 200



class ComputeNumericalHistogram(Resource):
    def get(self, attribute, bins, start, end, jobId):
        histo = np.zeros(int(bins))
        with open(json_dataset, 'r') as f:
            data = json.load(f)
            x = np.array([i["data"][attribute] for i in data])
            x = x[x >= float(start)]
            x = x[x <= float(end)]
            D = (float(end) - float(start)) / int(bins)
            for i in range(1, int(bins) + 1):
                bucket = x[x <= D * i + float(start)]
                bucket = bucket[bucket >= D * (i - 1) + float(start)]
                histo[i-1] = bucket.shape[0]
            with open(job_dataset(jobId), 'w') as f:
                f.writelines([str(int(j)) + '\n' for j in list(histo)])
        return '', 200

class Ping(Resource):
    def get(self):
        logger.info("Received ping. I 'm alive.")
        return '', 200


api.add_resource(Ping, '/api/ping')
api.add_resource(MapOperation, '/api/map-operation')
api.add_resource(GetDatasetSize, '/api/get-dataset-size/job-id/<jobId>')
api.add_resource(TriggerImportation, '/api/trigger-importation/job-id/<jobId>')
api.add_resource(ChangeData, '/api/update-dataset/<jobId>')
api.add_resource(DataStandardization, '/api/data-standardization')
api.add_resource(OpenRStudioServer, '/api/open-rstudio-server')

if __name__ == '__main__':
    app.run(debug=False, threaded=True, port=int(
        os.environ[PORT]), host="0.0.0.0")
