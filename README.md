# SCALE and MAMBA

This repository extends the [SCALE-MAMBA](https://github.com/KULeuven-COSIC/SCALE-MAMBA) repository to support external data providers. In particular it implements the protocol described in [Confidential Benchmarking based on Multiparty Computation](https://fc16.ifca.ai/preproceedings/10_Damgaard.pdf).

## Acknowledgements

The work in this project was supported by ["Athena" RC](https://www.athena-innovation.gr/en) and partially supported by the [European Union’s Horizon 2020](https://ec.europa.eu/programmes/horizon2020/en/) research and innovation programme under grant agreement No. 732907 (["My Health, My Data"](http://www.myhealthmydata.eu/why-mhmd/) and grant agreement No. \_\_ ["Human Brain Project"]).

## Components

SMPC is a cryptographic primitive where a set of computing nodes perform a computation of some function f over their private set of inputs revealing nothing but the output of the function f. SMPC can play a crucial role for the security and integrity in federated dataset processing especially when combined with differential privacy techniques to ensure data privacy. This is because SMPC allows computations on data in an encrypted form. It enables a group to compute large-scale aggregates or other properties of their distributed data without the need for a trusted third-party to collect said data. When combined with differential privacy it can ensure global differential privacy level utility guarantees with the same privacy guarantees as local differential privacy.

The SMPC engine has been developed on top of the open source SCALE-MAMBA software [1] and additional functionalities have been built to support secure importation of data. Our software runs the SPDZ protocol [2] which allows us to speed up computation times by running a lot of the required SMPC computations in an “offline” phase before an actual request is made to the system. MPC computations are implemented in the MAMBA programming language and support different aggregation operations including sum, multiplication, min/max operation and disjoint union. The engine supports input of up to 9 decimal digits and is built to work with vectors of arbitrary length.

The system can be analysed in three main components: coordinator, SMPC node and client node. The coordinator exposes a restful API for users and other programs to trigger SMPC computations. The SMPC nodes run the MPC protocol and the client nodes run the importer protocol to securely import data into the SMPC. The client node implements a restful API, only exposed on localhost, to enable other programs (e.g. MIP NODE service) to specify data to be imported for an upcoming job. Each SMPC job has a global unique identifier associated with it, and this is used to retrieve results as well as to specify which data should be used for each computation. The SMPC engine is designed to support aggregation of vectors which can be used for the implementation of various distributed algorithms such as gradient descent, and statistical computations (e.g. mean). The coordinator and client nodes are lightweight programs and do not demand a lot of computational resources (e.g. memory, cpu). The SMPC nodes can be more demanding in terms of memory and cpu.

## Run

docker-compose -f docker-compose.win.yml up

## License

MIT License as described in LICENSE file
