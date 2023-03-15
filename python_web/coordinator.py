import os
import threading
from time import sleep
import time
from redis import client
import flask
from flask import Flask, request
from flask_restful import Resource, Api, abort
from multiprocessing import Process
import requests
from auxfiles.appconsts import *
import json
from ctypes import c_char_p
from threading import Thread, Timer
from flask_cors import CORS
from coordinator_auxilliary import *
from auxfiles.customLogger import Logger
import redis
from redlock import Redlock
import traceback

logger = Logger(['root', 'client'])
logger.info("Coordinator Initialized.")

app = Flask(__name__)
api = Api(app)
CORS(app, resources={r"/api/*": {"origins": "*"}})

poll_time = 1

logger.info("Redis server is {0}, {1}, {2}".format(
    os.environ[REDIS_HOST], os.environ[REDIS_PORT], os.environ[REDIS_PSWD]))

class RedisClient:
    __lock_manager = None
    __r_queue = None
    __r_returns = None
    __r_results = None

    @staticmethod
    def lock_manager():
        if not RedisClient.__lock_manager:
            RedisClient.__lock_manager = Redlock([{"host": os.environ[REDIS_HOST],
                         "port": os.environ[REDIS_PORT],
                         "password": os.environ[REDIS_PSWD],
                         "db": 0}])
        return RedisClient.__lock_manager
    
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
    def r_returns():
        if not RedisClient.__r_returns:
            RedisClient.__r_returns = redis.Redis(
                host=os.environ[REDIS_HOST],
                port=os.environ[REDIS_PORT],
                password=os.environ[REDIS_PSWD],
                db=1)
        return RedisClient.__r_returns
    
    @staticmethod
    def r_results():
        if not RedisClient.__r_results:
            RedisClient.__r_results = redis.Redis(
                host=os.environ[REDIS_HOST],
                port=os.environ[REDIS_PORT],
                password=os.environ[REDIS_PSWD],
                db=2)
        return RedisClient.__r_results

db_url = os.environ[DB_URL]
CONNECTION_STRING = "mongodb://{1}:{2}@{0}/agoradb?authSource=admin&readPreference=primary&directConnection=true&ssl=false".format(
    db_url, os.environ[DB_UNAME], os.environ[DB_PSWD])
logger.info("Database url: {0}".format(CONNECTION_STRING))

try:
    logger.info(
        'Connected to redis at "{0}": queue {1}, returns {2}, results {3}'
        .format(os.environ[REDIS_HOST],
                RedisClient.r_queue().ping(), RedisClient.r_returns().ping(), RedisClient.r_results().ping())
    )
except redis.exceptions.ConnectionError as r_con_error:
    logger.critical('Redis connection error')
    # handle exception

logger.debug("Player 2 should be running at: {0}".format(
    os.environ[PLAYER_REPO_2]))
logger.debug("Player 1 should be running at: {0}".format(
    os.environ[PLAYER_REPO_1]))
logger.debug("Player 0 should be running at: {0}".format(
    os.environ[PLAYER_REPO_0]))

PlayersRepo = {
    "2": os.environ[PLAYER_REPO_2],
    "1": os.environ[PLAYER_REPO_1],
    "0": os.environ[PLAYER_REPO_0]
}


def mark_computation_failed(job_id, message):
    current = json.loads(RedisClient.r_results().get(job_id))
    RedisClient.r_results().set(
        job_id,
        json.dumps({
            JobId: job_id,
            Message: "Failed computation: {0}".format(message),
            "version": current["version"] if "version" in current else 0,
            ComputationOutput: "Error",
            Status: JobStatus.FAILED,
            ComputationType_: current[ComputationType_]
        })
    )

# def unlock(jobId, queue_item):
#     logger.info("Unlocking thread {0}".format(threading.current_thread().ident))
#     while 1:
#         lock_acquired = lock_manager.lock(RESULT_LOCK, 2000)
#         if lock_acquired:
#             current_result = json.loads(r_results.get(jobId))
#             if current_result[Status] == JobStatus.RUNNING and "version" in current_result and current_result["version"] == queue_item["version"]:
#                 logger.info("Irregular unlock")
#                 mark_computation_failed(
#                     str(queue_item[JobId]),
#                     "A communication error lead to the job being aborted."
#                 )
#                 r_queue.set("lock", 1)
#                 return
#             else:
#                 logger.info("Job exited normally. stopping thread {0}".format(threading.current_thread().ident))
#                 return


unlock_timeout = 20


def queue_listen():
    logger.info("Starting background queue listener")
    c = 0
    while 1:
        lock_acquired = RedisClient.lock_manager().lock(LOCK_NAME, 2000)
        if lock_acquired:
            try:
                tmpl = RedisClient.r_queue().get("lock")
                try:
                    lock_value = int(tmpl) if tmpl is not None else None
                except ValueError:
                    lock_value = tmpl
                # logger.debug("Lock is {0}.".format(lock_value))
                if lock_value == 1:
                    c = 0
                    queue_item = RedisClient.r_queue().lpop('queue:smpc')
                    if queue_item is None:
                        RedisClient.lock_manager().unlock(lock_acquired)
                        sleep(poll_time)
                    else:
                        queue_item = json.loads(queue_item)
                        jobId = str(queue_item[JobId])
                        try:
                            job_result = json.loads(RedisClient.r_results().get(jobId))
                            job_result[Status] = JobStatus.RUNNING
                            logger.info(
                                "Updating job ... {0}".format(job_result))
                            RedisClient.r_results().set(jobId, json.dumps(
                                job_result))
                            computation_input = (
                                jobId, queue_item['clients'], str(queue_item[ComputationType_]))
                            logger.debug("Read {0} from queue".format(
                                computation_input))
                            ret = trigger_computation(*computation_input)
                            # timerThread = Timer(unlock_timeout, unlock, (jobId, queue_item))
                            # timerThread.start()
                            if ret is not None and ret[1] != 200:
                                mark_computation_failed(
                                    jobId, ret[0]["message"])
                                # timerThread.cancel()
                                RedisClient.r_queue().set("lock", 1)
                        except Exception:
                            logger.error(
                                "Error in triggering computation. Ending job: {0}".format(
                                    traceback.format_exc())
                            )
                            try:
                                logger.error(
                                    "JobId is {0} result found was {1}".format(
                                        jobId,
                                        RedisClient.r_results().get(jobId)
                                    )
                                )
                            except Exception:
                                logger.error(
                                    "Error in retrieving result for job {0}".format(
                                        jobId)
                                )
                            mark_computation_failed(
                                str(queue_item[JobId]),
                                "Failed to trigger computation."
                            )
                            RedisClient.r_queue().set("lock", 1)
                elif lock_value == 0:
                    logger.info("System is busy. Waiting...")
                    c += 1
                    if c > 50:
                        logger.info("System is still busy. Aborting...")
                        RedisClient.r_queue().set("lock", 1)
                        c = 0
                    sleep(poll_time)
                else:
                    logger.info(
                        "SMPC sent abort signal: Lock is {0}.".format(lock_value))
                    c = 0
                    try:
                        mark_computation_failed(
                            lock_value,
                            "4SMPC could not complete computation."
                        )
                    except Exception:
                        logger.error("Error in marking computation failed: {0}".format(
                            traceback.format_exc()
                        ))
                    RedisClient.r_queue().set("lock", 1)
                RedisClient.lock_manager().unlock(lock_acquired)
            except Exception:
                logger.error("Error in queue listener: {0}".format(
                    traceback.format_exc()))
                RedisClient.lock_manager().unlock(lock_acquired)


@app.before_first_request
def start_routine():
    RedisClient.r_queue().set("lock", 1)
    p = Process(target=queue_listen, args=())
    p.start()


class GetAllPlayers(Resource):
    def get(self):
        return [{"id": k, "ip": PlayersRepo[k]} for k in PlayersRepo]


class GetAllClientCerts(Resource):
    def get(self):
        dbconn = get_database()
        clients = dbconn['agoradb']['clients']
        cursor = clients.find({})
        c = [{'id': cl[u'id'], 'crt': cl[u'crt']} for cl in list(cursor)]
        print(c)
        return c


class RegisterSMPCClientNode(Resource):
    def post(self):
        dbconn = get_database()
        json_data = request.get_json(force=True)
        if ClientId not in json_data.keys():
            logger.error("Received invalid client request".format(
                json_data[ClientId]))
            abort(400)
        logger.info("Received client request with id {0}".format(
            json_data[ClientId]))
        ip_address = flask.request.remote_addr
        clients = dbconn['agoradb']['clients']
        exists = clients.find_one({"id": json_data[ClientId]}, {"id": 1})
        dbconn.close()
        if exists is None:
            insert_client_to_db(
                json_data[ClientId], ip_address, json_data["port"], json_data["crt"])
            logger.info("Client entry added: clientId is {0}".format(
                json_data[ClientId]))
            for k in ['2', '1', '0']:
                try:
                    r = requests.post(PlayersRepo[k] + "/api/get-client-certificate",
                                      json={"client_id": json_data[ClientId], "crt": json_data["crt"]})
                    if r.status_code != 200:
                        raise requests.ConnectionError
                    logger.info(
                        "Succesfully sent client crt to smpc node {0}".format(k))
                except requests.ConnectionError:
                    logger.error(
                        "Failed to connect to smpc node with id {0}, at {1}. Aborting...".format(k, PlayersRepo[k]))
        else:
            if "force" in json_data.keys() and json_data["force"] == True:
                clients.remove({"id": json_data[ClientId]})
                insert_client_to_db(
                    json_data[ClientId], ip_address, json_data["port"], json_data["crt"])
                logger.info("Client update for clientId {0}".format(
                    json_data[ClientId]))
                for k in ['2', '1', '0']:
                    try:
                        r = requests.post(PlayersRepo[k] + "/api/get-client-certificate",
                                          json={"client_id": json_data[ClientId], "crt": json_data["crt"]})
                        if r.status_code != 200:
                            raise requests.ConnectionError
                        logger.info(
                            "Succesfully sent client crt to smpc node {0}".format(k))
                    except requests.ConnectionError:
                        logger.error(
                            "Failed to connect to smpc node with id {0}, at {1}. Aborting...".format(k, PlayersRepo[k]))
            else:
                logger.info("Client entry creation (clientId was {0}) failed because of conflict".format(
                    json_data[ClientId]))
                return {"message": "Client entry creation (clientId was {0}) failed because of conflict".format(
                    json_data[ClientId])}, 409


def get_all_clients():
    dbconn = get_database()
    clients = dbconn['agoradb']['clients']
    cursor = clients.find({})
    c = [{'id': cl[u'id']} for cl in list(cursor)]
    return c


def trigger_computation(jobId, client_list, computation_type):
    RedisClient.r_queue().set("lock", 0)
    ClientsRepo = get_client_repo(client_list)
    if ClientsRepo == 1:
        logger.error("The requested clients were not connected. Aborting...")
        return {"message": "The requested clients were not connected. Aborting..."}, 400
    dataset_size = None
    for i in client_list:
        try:
            clientUrl = ClientsRepo[i] + \
                "/api/get-dataset-size/job-id/{0}".format(jobId)
            r = requests.get(clientUrl)
            logger.info("Response from client at {0} is {1}".format(
                clientUrl, r.status_code))
            if r.status_code != 200:
                raise requests.ConnectionError
            if dataset_size is not None:
                if dataset_size != int(r.json()):
                    logger.error("Clients reported different dataset sizes [Client {0} said {1}, previously got {2}]. Aborting...".format(
                        i, str(r.json()), dataset_size))
                    return {"message": "Clients reported different dataset sizes [Client {0} said {1}, previously got {2}]. Aborting...".format(
                        i, str(r.json()), dataset_size)}, 409
                dataset_size = max(dataset_size, int(r.json()))
            else:
                dataset_size = int(r.json())
            logger.info(
                "Succesfully got dataset size from client with id {0}".format(i))
        except requests.ConnectionError:
            logger.error(
                "Failed to get dataset from client with id {0}. Aborting...".format(i))
            return {"message": "Failed to get dataset from client with id {0}. Aborting...".format(i)}, 404
        except Exception:
            logger.error("Internal error. Aborting... Detailed exception: {0}".format(
                traceback.format_exc()))
            return {"message": "Internal error. Aborting... Detailed exception: {0}".format(
                traceback.format_exc())}, 500
    for k in ['2', '1', '0']:
        try:
            r = requests.post(PlayersRepo[k] + "/api/job-id/{0}/dataset-size/{1}/computation-type/{2}".format(
                str(jobId), dataset_size, computation_type), json={"clients": client_list})
            if r.status_code != 200:
                logger.error(
                    "Player {0} rejected trigger_computation request. Aborting...".format(k))
                raise requests.ConnectionError
            logger.info("Succesfully connected to smpc node {0}".format(k))
        except requests.ConnectionError:
            logger.error(
                "Failed to connect to smpc node with id {0}, at {1}. Aborting...".format(k, PlayersRepo[k]))
            return {"message": "Failed to connect to smpc node with id {0}, at {1}. Aborting...".format(k, PlayersRepo[k])}, 404


class PreComputePoll(Resource):
    def post(self, jobId):
        logger.info("Received computation request. Triggering SMPC...")
        json_data = request.get_json(force=True)
        if ComputationType_ not in json_data.keys():
            return {Message: "Specify computation type", Status: 400}, 400
        if ReturnUrl in json_data.keys():
            logger.info("Setting returl url for {0}".format(jobId))
            RedisClient.r_returns().set(jobId, json_data[ReturnUrl])
        # exists = r_results.get(jobId)
        # if exists is not None and not jobId.startswith("testKey"):
        #     return {Message: "Job id exists.", Status: 409}, 409
        if "clients" not in json_data.keys():
            return {Message: "No clients specified.", Status: 400}, 400
        if not isinstance(json_data['clients'], list):
            return {Message: "A list of client ids should be provided.", Status: 400}, 400
        ClientsRepo = get_client_repo(json_data['clients'])
        if ClientsRepo == 1:
            logger.error(
                "The requested clients were not connected. Aborting...")
            return {"message": "The requested clients were not connected. Aborting..."}, 404
        if str(json_data[ComputationType_]).lower() not in ["sum", "product", "union", "min", "max", "fmin", "fsum", "fmax"]:
            logger.error(
                "Computation type not supported.")
            return {"message": "Computation type not supported."}, 400
        while 1:
            lock_acquired = RedisClient.lock_manager().lock(RESULT_LOCK, 2000)
            if lock_acquired:
                try:
                    tmpl = RedisClient.r_results().get(jobId)
                    current_result = json.loads(
                        tmpl) if tmpl is not None else None
                    if current_result is None or current_result[Status] == JobStatus.FAILED or current_result[Status] == JobStatus.COMPLETED:
                        version = time.time()
                        RedisClient.r_queue().rpush('queue:smpc', json.dumps(
                            {JobId: jobId, "version": version, ComputationType_: str(json_data[ComputationType_]).lower(), 'clients': json_data['clients']}))
                        RedisClient.r_results().set(jobId, json.dumps({
                            JobId: jobId,
                            "version": version,
                            ComputationType_: str(json_data[ComputationType_]).lower(),
                            Status: JobStatus.IN_QUEUE}))
                        return "", 200
                    else:
                        logger.error(
                            "Cannot queue job {0}. Job already in queue.".format(jobId))
                        return "", 409
                except Exception:
                    logger.error("Error queueing job: {0}".format(
                        traceback.format_exc()))
                    return "System cannot enqueu more jobs at the moment", 411


def trigger_categorical_histo_on_clients(k, attribute, noValues, jobId):
    logger.info("Sending cat histogram request to client at {0}".format(
        get_client_url(k)))
    r = requests.get(get_client_url(k) + "/api/compute-histogram/attribute/{0}/values/{1}/jobId/{2}".format(
        str(attribute), str(noValues), jobId))
    if r.status_code != 200:
        return "", 500


def trigger_numerical_histo_on_clients(k, attribute, bins, start, stop, jobId):
    r = requests.get(get_client_url(k) + "/api/compute-numerical-histogram/attribute/{0}/bins/{1}/start/{2}/end/{3}/jobId/{4}".format(
        str(attribute), str(bins), str(start), str(stop), jobId))
    if r.status_code != 200:
        return "", 500


def trigger_logistic_on_clients(k, jobId, json_data):
    r = requests.post(get_client_url(
        k) + "/api/logistic-regression/job-id/{0}".format(jobId), json=json_data)
    if r.status_code != 200:
        return "", 500


class CategoricalHistogramTrigger(Resource):
    def get(self, attribute, noValues, jobId, clients):
        clients_list = clients.split(".")
        threads = []
        for k in clients_list:
            thread = Thread(target=trigger_categorical_histo_on_clients, args=(
                k, attribute, noValues, jobId))
            threads.append(thread)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return trigger_computation(jobId, clients)


class NumericalHistogramTrigger(Resource):
    def get(self, attribute, bins, start, stop, jobId, clients):
        clients_list = clients.split(".")
        threads = []
        for k in clients_list:
            thread = Thread(target=trigger_numerical_histo_on_clients, args=(
                k, attribute, bins, start, stop, jobId))
            threads.append(thread)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        trigger_computation(jobId, clients)
        return "", 200


class LogisticRegressionTrigger(Resource):
    def post(self, jobId, clients):
        json_data = request.get_json(force=True)
        clients_list = clients.split(".")
        threads = []
        for k in clients_list:
            thread = Thread(target=trigger_logistic_on_clients, args=(
                k, jobId, json_data))
            threads.append(thread)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        trigger_computation(jobId, clients)


class GetAllClients(Resource):

    def mapLocalToDocker(self, ip):
        if ip.startswith("http://172."):
            return "http://" + "host.docker.internal:" + ip.split(":")[-1]
        return ip

    def get(self):
        clientsRepo = get_client_repo([i['id'] for i in get_all_clients()])
        return [{'id': j, 'ip': self.mapLocalToDocker(clientsRepo[j])} for j in clientsRepo], 200


class SetReturnUrl(Resource):
    def get(self, jobId):
        logger.info("Getting return url for {0}".format(jobId))
        try:
            return {"url": RedisClient.r_returns().get(jobId)}, 200
        except Exception:
            logger.error("Error getting return url for {0}".format(jobId))
            return {"message": "Error getting return url for {0}".format(jobId)}, 503

    def post(self, jobId):
        logger.info("Setting return url for {0}".format(jobId))
        json_data = request.get_json(force=True)
        try:
            RedisClient.r_returns().set(jobId, str(json_data['url']))
            return "", 200
        except Exception:
            logger.error("Error setting return url for {0}".format(jobId))
            return {"message": "Error setting return url for {0}".format(jobId)}, 503


def normalize_union(result):
    output = []
    if int(result[-1]) == 1:
        output += ['0']
    output += [i for i in result[:-1] if int(i) != 0]
    return output


def normalize_floats(result):
    try:
        if str(result[ComputationType_]).startswith("f"):
            tmp = []
            for i in range(len(result[ComputationOutput])/2):
                tmp.append(int(result[ComputationOutput][2*i]) +
                           1e-9 * int(result[ComputationOutput][2*i + 1]))
            result[ComputationOutput] = tmp
    except Exception:
        logger.error("Error normalizing floats: {0}".format(
            traceback.format_exc()))
    return result


class Return(Resource):
    def post(self, json_data=None):
        logger.info("Received result from {0}".format(
            flask.request.remote_addr))
        if json_data is None:
            json_data = request.get_json(force=True)
        result = {}
        for k in json_data:
            if str(k) == JobId:
                result[str(k)] = str(json_data[k])
            else:
                if json_data[k] is None:
                    result[str(k)] = None
                else:
                    result[str(k)] = [str(i) for i in json_data[k]]
        should_send = False
        lock_acquired = RedisClient.lock_manager().lock(RESULT_LOCK, 2000)
        if lock_acquired:
            try:
                current_result = json.loads(RedisClient.r_results().get(result[JobId]))
                result[ComputationType_] = current_result[ComputationType_]
                logger.debug("Current result is {0}".format(current_result))
                if current_result[Status] == JobStatus.RUNNING:
                    logger.info("Computation jobId {0} result is {1}".format(
                        result[JobId], result))
                    if result[ComputationOutput] is None:
                        logger.error(
                            "Computation result is None. JobId: {0}".format(result[JobId]))
                        mark_computation_failed(result[JobId], "SMPC aborted.")
                        should_send = True
                    else:
                        result = normalize_floats(result)
                        result[Validation] = 1
                        result["version"] = current_result["version"]
                        result[Status] = JobStatus.VALIDATING
                        if current_result[ComputationType_] == ComputationType.U:
                            result[ComputationOutput] = normalize_union(
                                result[ComputationOutput])
                            logger.info("After normalizing we have: {0}".format(
                                result[ComputationOutput]))
                            logger.debug(normalize_union(
                                result[ComputationOutput]))
                        logger.info(
                            "Setting result. JobId: {0}".format(result[JobId]))
                        RedisClient.r_results().set(result[JobId], json.dumps(result))
                elif current_result[Status] == JobStatus.FAILED:
                    pass
                else:
                    try:
                        result = normalize_floats(result)
                        logger.debug("Comparing ... {0} =?= {1}".format(
                            current_result[ComputationOutput], result[ComputationOutput]))
                        if current_result[ComputationOutput] == result[ComputationOutput] or (
                            current_result[ComputationOutput] == normalize_union(
                                result[ComputationOutput]) and current_result[ComputationType_] == ComputationType.U
                        ):
                            logger.info("Result valid by players: {0}".format(
                                current_result[Validation] + 1))
                            result[Validation] = int(
                                current_result[Validation]) + 1
                            result[Status] = JobStatus.VALIDATING
                        else:
                            result[Status] = JobStatus.FAILED
                            should_send = True
                        if result[Validation] > 1:
                            result[Status] = JobStatus.COMPLETED
                            should_send = True
                        result[ComputationOutput] = current_result[ComputationOutput]
                        RedisClient.r_results().set(result[JobId], json.dumps(result))
                    except Exception as e:
                        logger.error("Error: {0}".format(e))
                        mark_computation_failed(
                            result[JobId], "Failed to validate result.")
                        should_send = True
            except Exception:
                logger.error(
                    "Error during result processing: {0}".format(traceback.format_exc()))
                mark_computation_failed(
                    result[JobId], "Failed to validate result.")
                should_send = True
            job_return_url = RedisClient.r_returns().get(result[JobId])
            logger.info("Will send result: {0}".format(
                should_send and job_return_url is not None))
            if (should_send):
                RedisClient.r_queue().set("lock", 1)
            if (should_send and job_return_url is not None):
                try:
                    logger.info(
                        "Sending result to return url. {0}".format(job_return_url))
                    requests.post(
                        job_return_url,
                        json=result
                    )
                except requests.ConnectionError:
                    logger.error(
                        "Failed to connect to remote endpoint"
                    )
            RedisClient.lock_manager().unlock(lock_acquired)
            return "", 200
        else:
            return self.post(json_data)


class ServeResult(Resource):
    def get(self, jobId):
        logger.info("Fetching result for jobId {0}".format(jobId))
        if jobId is None:
            logger.error("Invalid request. Specify jobId.")
            return "", 400
        try:
            job_result = RedisClient.r_results().get(jobId)
            if job_result is None:
                return "", 204
            return json.loads(job_result), 200
        except Exception:
            logger.error("Error getting return url for {0}".format(jobId))
            return {"message": "Error getting return url for {0}".format(jobId)}, 503


class Ping(Resource):
    def get(self):
        logger.info("Received ping. I 'm alive.")
        return 200


api.add_resource(
    GetAllClientCerts, '/api/get-all-client-certs')
api.add_resource(
    PreComputePoll, '/api/secure-aggregation/job-id/<jobId>')
api.add_resource(
    CategoricalHistogramTrigger, '/api/compute-histogram/attribute/<attribute>/values/<noValues>/job-id/<jobId>/clients/<clients>')
api.add_resource(NumericalHistogramTrigger,
                 '/api/compute-numerical-histogram/attribute/<attribute>/bins/<bins>/start/<start>/end/<stop>/job-id/<jobId>/clients/<clients>')
api.add_resource(SetReturnUrl, '/api/set-return-url/job-id/<jobId>')
api.add_resource(Ping, '/api/ping')
api.add_resource(ServeResult, '/api/get-result/job-id/<jobId>')
api.add_resource(RegisterSMPCClientNode, '/api/register-client')
api.add_resource(Return, '/api/result')
api.add_resource(LogisticRegressionTrigger,
                 '/api/logistic-regression/job-id/<jobId>/clients/<clients>')
api.add_resource(GetAllPlayers, '/api/get-all-players')
api.add_resource(GetAllClients, '/api/get-all-clients')

if __name__ == '__main__':
    app.run(debug=True, threaded=True, port=12314, host="0.0.0.0")
