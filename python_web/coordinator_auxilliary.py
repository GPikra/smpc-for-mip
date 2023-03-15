from Database import get_database
from enum import Enum


class ComputationType(Enum):
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    PROD = "product"
    U = "union"
    fSUM = "fsum"
    fPROD = "fprod"
    fMIN = "fmin"
    fMAX = "fmax"


class JobStatus(Enum):
    IN_QUEUE = "IN_QUEUE"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def get_client_url(client_id):
    dbconn = get_database()
    db_clients = dbconn["agoradb"]['clients']
    exists = db_clients.find_one({"id": client_id})
    if (exists == None):
        return 1
    dbconn.close()
    return "http://{0}:{1}".format(exists["ip_address"], exists["port"])


def get_client_repo(client_list):
    dbconn = get_database()
    db_clients = dbconn["agoradb"]['clients']
    ClientsRepo = {}
    for c in client_list:
        exists = db_clients.find_one({"id": c})
        if exists is None:
            return 1
        ClientsRepo[c] = "http://{0}:{1}".format(
            exists["ip_address"], exists["port"])
    dbconn.close()
    return ClientsRepo


def insert_client_to_db(client_id, ip_address, port, crt):
    dbconn = get_database()
    clients = dbconn["agoradb"]['clients']
    clients.insert_one(
        {
            "id": client_id,
            "ip_address": ip_address,
            "port": port,
            "crt": crt
        })
    dbconn.close()
