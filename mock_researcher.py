from time import sleep
from flask import Flask, jsonify, request
from flask_cors.extension import CORS
from flask_restful import Resource, Api
from multiprocessing import Process, Manager
from player_auxilliary import generate_and_compile, run_smpc_computation
import json
import argparse
import numpy as np
from logistic_regressor import model_update
import requests

app = Flask(__name__)
api = Api(app)
manager = Manager()
parameterList = manager.list([0, 0, 0, 0, 0])

CORS(app, resources={r"/api/*": {"origins": "*"}})
class TriggerComputation(Resource):
    def post(self):
        json_data = request.get_json(force=True)
        jobId = str(json_data['jobId'])
        print(json_data)
        # if len(jobId.split(".")) > 1:
        #     iter = int(jobId.split(".")[1])
        #     iter += 1
        #     jobId = jobId.split(".")[0] + "." + str(iter)
        # else:
        #     jobId +=".1"
        # grads = [int(i)*1e-5 for i in json_data["computation_output"][:-1]]
        # w = parameterList[:-1]
        # b = parameterList[-1]
        # w, b = model_update(w, b, grads)
        # for i in range(len(parameterList) - 1):
        #     parameterList[i] = w[i]
        # parameterList[-1] = b
        # print(parameterList)
        # requests.post(
        #         str("http://localhost:12314/api/logistic-regression/job-id/{0}/clients/0".format(jobId)),
        #         json={
        #             "w": w,
        #             "b": b
        #         }
        #     )



class Ping(Resource):
    def get(self):
        return 200

api.add_resource(Ping, '/api/ping')
api.add_resource(TriggerComputation, '/api/listen')
    
if __name__ == '__main__':
    app.run(debug=True, port=8223, host="0.0.0.0")