import numpy as np
from sklearn.preprocessing import Normalizer

def sigmoid_activation(x):
    return 1/(1+np.exp(-x))


def weightInitialization(n_features):
    w = np.zeros((1, n_features))
    b = 0
    return w, b

def model_update(w, b, grads):
    return list(np.array(w) - 0.1 * np.array(grads[:-1])), b - 0.1 * grads[-1]

def model_optimize(w, b, X, Y):
    m = float(X.shape[0])

    X = Normalizer().fit_transform(X)
    # Prediction
    final_result = sigmoid_activation(np.dot(w, X.T)+b)
    Y_T = Y.T
    cost = (-1/m)*(np.sum((Y_T*np.log(final_result)) +
                          ((1-Y_T)*(np.log(1-final_result)))))
    #

    # Gradient calculation
    dw = (1/m)*(np.dot(X.T, (final_result-Y.T).T))
    db = (1/m)*(np.sum(final_result-Y.T))

    grads = {"dw": dw, "db": db}

    return grads, cost
