import os
import numpy as np
import json

keys = ["age",
        "ethnicity",
        "gender",
        "heartRate",
        "nipb",
        "respiratoryRate",
        "o2saturation"]

dists = [
    np.random.randint,
    np.random.randint,
    np.random.randint,
    lambda x: np.round(np.random.normal(80, 10), 2),
    lambda x: np.round(np.random.normal(60, 10), 2),
    lambda x: np.round(np.random.normal(25, 3), 2),
    lambda x: int(np.min([np.random.normal(99, 1), 100])),
]

params = [
    5,
    3,
    2,
    0,
    0,
    0,
    0
]

offset = 1
no_patients = 200


def main():
    dataset = [{"pk": offset * no_patients + i}
               for i in range(no_patients)]
    npArray = np.zeros((no_patients, 4))
    npArrayY = np.zeros((no_patients,))
    for outterIdx, datum in enumerate(dataset):
        schema = {}
        for idx, k in enumerate(keys):
            schema[k] = dists[idx](params[idx])
        npArray[outterIdx] = np.array(
            [   
                schema["heartRate"],
                schema["nipb"],
                schema["respiratoryRate"],
                schema["o2saturation"]
            ]
        )
        npArrayY[outterIdx] = schema["gender"]
        datum["data"] = schema
    with open(os.path.join('dataset', "numpy_dataset_{0}.npy".format(offset)), 'wb') as f:
        np.save(f, npArray)
    with open(os.path.join('dataset', "numpy_labels_{0}.npy".format(offset)), 'wb') as f:
        np.save(f, npArrayY)
    with open(os.path.join("dataset", "full_dataset_{0}.json".format(offset)), 'w') as f:
        json.dump(dataset, f)


if __name__ == "__main__":
    main()
