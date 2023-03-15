import subprocess
from time import sleep
import traceback
from flask import Flask, request
from flask_cors.extension import CORS
from flask_restful import Resource, Api
from threading import Timer
from multiprocessing import Process
from player_auxilliary import generate_and_compile, run_smpc_computation
import argparse
from auxfiles.customLogger import Logger
import os

from redlock import Redlock
from auxfiles.appconsts import *
from player_auxilliary import get_all_client_certs
import redis
logger = Logger(['root', 'client'])
logger.info("Player Initialized.")

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument(
    'player_id',
    metavar='id',
    type=int,
    nargs=1,
    help='Specify player Id'
)

args = parser.parse_args()
player_id = args.player_id[0]
app = Flask(__name__)
api = Api(app)

CORS(app, resources={r"/api/*": {"origins": "*"}})

class RedisClient:
    __r_queue = None
    __lock_manager = None
    @staticmethod
    def r_queue():
        if not RedisClient.__r_queue:
            RedisClient.__r_queue = redis.Redis(
                host=os.environ[REDIS_HOST],
                port=os.environ[REDIS_PORT],
                password=os.environ[REDIS_PSWD],
                db=0)
        return RedisClient.__r_queue
    
    @staticmethod
    def lock_manager():
        if not RedisClient.__lock_manager:
            RedisClient.__lock_manager = Redlock([{"host": os.environ[REDIS_HOST],
                         "port": os.environ[REDIS_PORT],
                         "password": os.environ[REDIS_PSWD],
                         "db": 0}])
        return RedisClient.__lock_manager

player2_url = os.environ[PLAYER_REPO_2].split("http://")[1].split(":")[0]
player1_url = os.environ[PLAYER_REPO_1].split("http://")[1].split(":")[0]
player0_url = os.environ[PLAYER_REPO_0].split("http://")[1].split(":")[0]
try:
    kill_timeout = int(os.environ[KILL_TIMEOUT])
except Exception:
    kill_timeout = 300
networkData = os.path.join(os.getcwd(), "Data", "NetworkData.txt")

with open(networkData, 'w') as f:
    f.write(
        "RootCA.crt\n3\n0 {0} Player0.crt P0\n1 {1} Player1.crt P1\n2 {2} Player2.crt P2\n0\n0".format(
            player0_url, player1_url, player2_url
        )
    )

while 1:
    try:
        client_crts = get_all_client_certs()
        for client in client_crts:
            logger.debug("Received from coordinator: {0}".format(client))
            client_id = client["id"]
            with open(os.path.join(os.getcwd(), "Cert-Store", "Client{0}.crt".format(client_id)), "w") as f:
                f.write(client['crt'])
                logger.info("Wrote certificate")
        break
    except Exception as e:
        logger.error("Could not get client certs: {0}".format(
            traceback.format_exc()))
        logger.error("Retrying in 2 seconds")
        sleep(2)


class GetClientCertificate(Resource):
    def post(self):
        json_data = request.get_json(force=True)
        logger.debug("Received from coordinator: {0}".format(json_data))
        client_id = json_data["client_id"]
        with open(os.path.join(os.getcwd(), "Cert-Store", "Client{0}.crt".format(client_id)), "w") as f:
            f.write(json_data['crt'])
            logger.info("Wrote certificate")


def kill_process(p, lock_manager, lock_acquired, jobId):
    c = 0
    while c <= 10:
        c += 1
        lock_acquired = lock_manager.lock(LOCK_NAME, 2000)
        if lock_acquired:
            if p.is_alive():
                p.terminate()
                RedisClient.r_queue().set("lock", jobId)
                logger.info("Process killed after timeout")
            lock_manager.unlock(lock_acquired)
            return
        sleep(1)


class TriggerComputation(Resource):
    def post(self, jobId, datasetSize, computationType):
        json_data = request.get_json(force=True)
        clients = [str(i) for i in json_data['clients']]
        logger.info("Received trigger computation request {1}. Clients {0}".format(
            clients, jobId))
        c = 0
        while c < 10:
            lock_acquired = RedisClient.lock_manager().lock("lock:smpc", 2000)
            if lock_acquired:
                # kill all processes running Player.x                
                logger.info("Preparing new computation. Player process exists: {0}".format(os.popen("pidof Player.x").read()))
                logger.info("Preparing new computation. Port users: {0}".format(os.popen("lsof -i :{0}".format(6000+player_id)).read()))
                return_code = subprocess.call("kill -15 $(pidof Player.x)", shell=True)                
                if return_code < 2:                
                    logger.info("Killed all Player.x processes. Return code: {0}".format(return_code))
                sleep(5)              
                logger.info("[AFTER KILL returncode={1}] Player process exists: {0}".format(os.popen("pidof Player.x").read(), return_code))
                logger.info("[AFTER KILL] Port users: {0}".format(os.popen("lsof -i :{0}".format(6000+player_id)).read()))
                try:
                    generate_and_compile(
                        clients, datasetSize, computationType, jobId)
                    p = Process(target=run_smpc_computation, args=(
                        player_id, clients, jobId, computationType, datasetSize))
                    p.start()
                    # logger.info("Started Timer")
                    timerThread = Timer(kill_timeout, kill_process,
                                        (p, RedisClient.lock_manager(), lock_acquired, jobId))
                    timerThread.start()
                    logger.info("[{1}] run_smpc output code is: {0}".format(
                        p.exitcode, jobId))
                    if p.exitcode is not None and p.exitcode != 0:
                        raise ValueError
                    return '', 200
                except Exception as e:
                    logger.error("[{1}] An unexpected error occured: {0}".format(
                        traceback.format_exc(), jobId))
                    return 500
            else:
                sleep(2)
                c += 1
        logger.error("An unexpected error occured: {0}".format(
            traceback.format_exc()))
        return 500


class Ping(Resource):
    def get(self):
        logger.info("Received ping. I 'm alive.")
        return 200


api.add_resource(GetClientCertificate, '/api/get-client-certificate')
api.add_resource(Ping, '/api/ping')
api.add_resource(TriggerComputation,
                 '/api/job-id/<jobId>/dataset-size/<datasetSize>/computation-type/<computationType>')

if __name__ == '__main__':
    app.run(debug=True, threaded=True, port=int(
        os.environ[PORT])+player_id, host="0.0.0.0")
