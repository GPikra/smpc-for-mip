# SCALE and MAMBA

This repository extends the [SCALE-MAMBA](https://github.com/KULeuven-COSIC/SCALE-MAMBA) repository to support external data providers. In particular it implements the protocol described in [Confidential Benchmarking based on Multiparty Computation](https://fc16.ifca.ai/preproceedings/10_Damgaard.pdf).

## Acknowledgements

The work in this project was supported by ["Athena" RC](https://www.athena-innovation.gr/en) and partially supported by the [European Union’s Horizon 2020](https://ec.europa.eu/programmes/horizon2020/en/) research and innovation programme under grant agreement No. 732907 (["My Health, My Data"](http://www.myhealthmydata.eu/why-mhmd/)) and this research was also supported by the EBRAINS research infrastructure, funded from the European Union’s Horizon 2020 Framework Programme for Research and Innovation under the Specific Grant Agreement No. 945539 (Human Brain Project SGA3)

## Components

SMPC is a cryptographic primitive where a set of computing nodes perform a computation of some function f over their private set of inputs revealing nothing but the output of the function `f`. SMPC can play a crucial role for the security and integrity in federated dataset processing especially when combined with differential privacy techniques to ensure data privacy. This is because SMPC allows computations on data in an encrypted form. It enables a group to compute large-scale aggregates or other properties of their distributed data without the need for a trusted third-party to collect said data. When combined with differential privacy it can ensure global differential privacy level utility guarantees with the same privacy guarantees as local differential privacy.

The SMPC engine has been developed on top of the open source SCALE-MAMBA software [1] and additional functionalities have been built to support secure importation of data. Our software runs the SPDZ protocol [2] which allows us to speed up computation times by running a lot of the required SMPC computations in an “offline” phase before an actual request is made to the system. MPC computations are implemented in the MAMBA programming language and support different aggregation operations including sum, multiplication, min/max operation and disjoint union. The engine supports input of up to 9 decimal digits and is built to work with vectors of arbitrary length.

The system can be analysed in three main components: coordinator, SMPC node and client node. The coordinator exposes a restful API for users and other programs to trigger SMPC computations. The SMPC nodes run the MPC protocol and the client nodes run the importer protocol to securely import data into the SMPC. The client node implements a restful API, only exposed on localhost, to enable other programs (e.g. MIP NODE service) to specify data to be imported for an upcoming job. Each SMPC job has a global unique identifier associated with it, and this is used to retrieve results as well as to specify which data should be used for each computation. The SMPC engine is designed to support aggregation of vectors which can be used for the implementation of various distributed algorithms such as gradient descent, and statistical computations (e.g. mean). The coordinator and client nodes are lightweight programs and do not demand a lot of computational resources (e.g. memory, cpu). The SMPC nodes can be more demanding in terms of memory and cpu.

## Differential Privacy


The following document serves as a basic guide for the use of differential privacy with the MIP SMPC engine. When triggering a computation request through the endpoint 

```
http://{{coordinator}}:{{coordinator-port}}/api/secure-aggregation/job-id/{key}
```

With example body,
```
{
    "computationType": "sum",
    "returnUrl": "http://localhost:4100",
    "clients": ["ZuellingPharma"],    
    "dp": {
        "c": 1,
        "e": 1
    }
}
```


The “dp” optional attribute controls the differential privacy parameters. These are `c` for the L2 sensitivity of the underlying computation and `e` for the privacy budget `ε`. 

In general, `e>0`  is a free parameter controlling the privacy budget in the sense of differential privacy. A lower value of e will result in more noise being added to the computation and hence a higher privacy guarantee (though with lower utility). 

The parameter `c` should be computed based on the underlying computation. For example, for counting queries and in particular histograms, heatmaps etc, it is the case that `c=1`. For more complex queries the computation of `c` might not be very straightforward and we might need to resort to the clipping trick, whereby the values are clipped within an interval `[-δ, δ]` to enforce an upper bound on the sensitivity of `c=2δ`. In such cases `δ` should be chosen independently of the data and in a way that best approximates the actual range of values that the underlying variable takes.

The SMPC engine implements the Laplacian mechanism, adding to the computed result a sample from the `Lap(0, c/e)` distribution. Note that the variance of the noise scales with `c/e`. 
This provides a differential privacy guarantee of ε=e. 

The dp attribute takes additional optional parameters cs,es which allows one to pass arrays of `c` and `e` values which are applied to the result index wise. If the result has a higher dimension than the given array, the last value of the array is used for the remainder of the values. If the array has a higher dimension the redundant values are ignored. The arrays cs and es must have equal length.


## Run

docker-compose -f docker-compose.win.yml up
