import os
import pymongo as pm
from auxfiles.appconsts import DB_URL
from auxfiles.customLogger import Logger
from auxfiles.appconsts import DB_PSWD, DB_UNAME

db_url = os.environ[DB_URL]
CONNECTION_STRING = "mongodb://{1}:{2}@{0}/agoradb?authSource=admin&readPreference=primary&directConnection=true&ssl=false".format(
    db_url, os.environ[DB_UNAME], os.environ[DB_PSWD])
logger = Logger(['root', 'client'])

class MongoClient:
    __client = pm.MongoClient(CONNECTION_STRING)
    @staticmethod
    def get_client():
        if not MongoClient.__client:
            MongoClient.__client = pm.MongoClient(CONNECTION_STRING)
        return MongoClient.__client

def get_database():
    return MongoClient.get_client()


if __name__ == '__main__':
    dbaname = get_database()
    print("Success")
