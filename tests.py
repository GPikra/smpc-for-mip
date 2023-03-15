from collections import defaultdict
import json
from time import sleep
import requests

def post(url, data):
    try:
        return requests.post(
                url,
                json=data
            )
    except requests.ConnectionError:
        print("Failed to return result to {0}.".format(url))

def get(url):
    try:
        return requests.get(
                url
            )
    except requests.ConnectionError:
        print("Failed to return result to {0}.".format(url))

def get_json(url):
    try:
        r = requests.get(
                url
            )
        return r.json()
    except requests.ConnectionError:
        print("Failed to return result to {0}.".format(url))

x = 0
ct = ["sum", "fsum"]
stats = defaultdict(int)
while 1:    
    print("Trial no:", x)
    post("http://localhost:9000/api/update-dataset/testKey{0}".format(x), { 
        "type": "float",
        "data": 
        [
            11.9,
            2.0
        ]
    })
    r = post("http://localhost:12314/api/secure-aggregation/job-id/testKey{0}".format(x), { "computationType": ct[x % 2], "clients": ["ZuellingPharma"] })
    if r.status_code != 200:
        stats["canceledByTester"] += 1
        x += 1
        continue
    for _ in range(40):
        json_data = get_json("http://localhost:12314/api/get-result/job-id/testKey{0}".format(x))
        sleep(2)
        if json_data is not None:
            if json_data["status"] != "FAILED" and "computationOutput" in json_data:
                print("Result: {0}".format(json_data["computationOutput"]))
                stats["success"] += 1
                break
            if json_data["status"] == "FAILED":
                print(json_data)
                stats[json_data["message"]] += 1
                break
            print(json_data)
        else:
            stats["none"] += 1
    print("----------------------------------------------------------------")
    print(stats)
    x += 1



# x = 0
# ct = ["sum", "fsum"]
# stats = defaultdict(int)
# while 1:    
#     json_data = get_json("http://localhost:12314/api/get-result/job-id/testKey{0}".format(x))
#     if json_data is not None:
#         print(json_data)
#         if json_data["status"] != "FAILED" and "computationOutput" in json_data:
#             print("Result: {0}".format(json_data["computationOutput"]))
#             stats["success"] += 1
#         elif json_data["status"] == "FAILED":
#             print(json_data)
#             stats[json_data["message"]] += 1
#         else:
#             stats["none"] += 1
#     else:
#         stats["none"] += 1
#     print("----------------------------------------------------------------")
#     print(stats)
#     x += 1