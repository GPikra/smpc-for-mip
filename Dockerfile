# FROM gpikra/coordinator
# COPY . /SCALE-MAMBA
# ENV PATH="/local/openssl/bin/:${PATH}"
# ENV C_INCLUDE_PATH="/local/openssl/include/:${C_INCLUDE_PATH}"
# ENV CPLUS_INCLUDE_PATH="/local/openssl/include/:${CPLUS_INCLUDE_PATH}"
# ENV LIBRARY_PATH="/local/openssl/lib/:${LIBRARY_PATH}"
# ENV LD_LIBRARY_PATH="/local/openssl/lib/:${LD_LIBRARY_PATH}"
# ENV C_INCLUDE_PATH="/local/mpir/include/:${C_INCLUDE_PATH}"
# ENV CPLUS_INCLUDE_PATH="/local/mpir/include/:${CPLUS_INCLUDE_PATH}"
# ENV LIBRARY_PATH="/local/mpir/lib/:${LIBRARY_PATH}"
# ENV LD_LIBRARY_PATH="/local/mpir/lib/:${LD_LIBRARY_PATH}"
# ENV CPLUS_INCLUDE_PATH="/local/cryptopp/include/:${CPLUS_INCLUDE_PATH}"
# ENV LIBRARY_PATH="/local/cryptopp/lib/:${LIBRARY_PATH}"
# ENV LD_LIBRARY_PATH="/local/cryptopp/lib/:${LD_LIBRARY_PATH}"

# RUN cp CONFIG CONFIG.mine

# RUN echo 'ROOT = /SCALE-MAMBA' >> CONFIG.mine
# RUN echo 'OSSL = /local/openssl' >> CONFIG.mine
# RUN make clean
# WORKDIR /SCALE-MAMBA/src
# RUN make

FROM gpikra/coordinator:v7.0.7.3
WORKDIR /SCALE-MAMBA
RUN apt-get update -y && apt-get install lsof -y && apt-get install net-tools -y && apt-get install dsniff -y
COPY ./src /SCALE-MAMBA/src
RUN make clean
RUN make progs
RUN make
WORKDIR /SCALE-MAMBA
COPY ./logs /SCALE-MAMBA/logs
COPY ./dataset /SCALE-MAMBA/dataset
COPY ./Programs /SCALE-MAMBA/Programs
COPY ./python_web/auxfiles /SCALE-MAMBA/auxfiles
COPY ./python_web/logistic_regressor.py /SCALE-MAMBA/logistic_regressor.py
COPY ./python_web/coordinator_auxilliary.py /SCALE-MAMBA/coordinator_auxilliary.py
COPY ./python_web/coordinator.py /SCALE-MAMBA/coordinator.py
COPY ./python_web/player.py /SCALE-MAMBA/player.py
COPY ./python_web/Database.py /SCALE-MAMBA/Database.py
COPY ./python_web/player_auxilliary.py /SCALE-MAMBA/player_auxilliary.py
COPY ./python_web/client.py /SCALE-MAMBA/client.py
COPY ./mock_researcher.py /SCALE-MAMBA/mock_researcher.py
COPY ./requirements.txt /SCALE-MAMBA/requirements.txt
RUN pip install -r requirements.txt

# FROM system_base
# WORKDIR  /SCALE-MAMBA
# COPY ./python_web/auxfiles/config/logging.cfg /SCALE-MAMBA/python_web/auxfiles/config/logging.cfg

# FROM debian:stretch

# RUN apt-get update && apt-get upgrade -y
# RUN apt-get install -y \
#   gnupg2 \
#   yasm \
#   python \
#   python-pip \
#   gcc \
#   g++ \
#   cmake \
#   make \
#   curl \
#   wget \
#   apt-transport-https \
#   m4 \
#   zip \
#   unzip \
#   vim \
#   build-essential

# RUN mkdir SCALE-MAMBA
# COPY . /SCALE-MAMBA

# WORKDIR /SCALE-MAMBA
# RUN ./install_dependencies.sh /local


# WORKDIR /SCALE-MAMBA
# RUN pip install -r requirements.txt


# # ENTRYPOINT ["python", "coordinator.py"]
