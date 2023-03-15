import os
import signal
import subprocess
import time
from auxfiles.appconsts import *
from flask_restful import abort
import requests
import sys
from threading import Thread
from auxfiles.customLogger import Logger
from coordinator_auxilliary import get_client_url
from coordinator_auxilliary import ComputationType
import traceback

logger = Logger(['root', 'client'])
WAIT = '@'
OUTPUT_START = '# OUTPUT START:'
OUTPUT_END = "$ OUTPUT END"
# coordinator = "http://0.0.0.0:12314/api/result"
coordinator = os.environ[COORDINATOR_URL]


def get_all_client_certs():
    logger.info("Getting all client certs")
    try:
        r = requests.get(coordinator + "/api/get-all-client-certs")
        if r.status_code != 200:
            logger.error(
                "Unable to get all client certs from coordinator. Coordinator rejected.")
            raise requests.ConnectionError
        return r.json()
    except requests.ConnectionError:
        logger.error("Unable to connect to coordinator at {1}: {0}".format(
            traceback.format_exc(), coordinator + "/api/get-all-client-certs"))
        raise requests.ConnectionError
    except Exception:
        logger.error("Unexpected error occured: {0}".format(
            traceback.format_exc()))
        raise ValueError


def MPC_PROGRAM_NAME(computationType):
    if computationType == ComputationType.SUM:
        return "aa"
    if computationType == ComputationType.MIN:
        return "bb"
    if computationType == ComputationType.MAX:
        return "cc"
    if computationType == ComputationType.PROD:
        return "dd"
    if computationType == ComputationType.U:
        return "ee"
    if computationType == ComputationType.fSUM:
        return "aa"
    if computationType == ComputationType.fMIN:
        return "ff"
    if computationType == ComputationType.fMAX:
        return "gg"
    else:
        logger.error("Did not receive implemented computation")
        abort(400)
        return 1


def MPC_PROGRAM(
    computationType): return "Programs/{0}/{0}.mpc".format(MPC_PROGRAM_NAME(computationType))


def cmd_compile_player(computationType): return ['python', 'compile.py',
                                                 'Programs/{0}'.format(MPC_PROGRAM_NAME(computationType))]


def trigger_importation(client, jobId):
    logger.info("Triggering importation")
    try:
        logger.debug(get_client_url(client))
        r = requests.get(
            get_client_url(client) + "/api/trigger-importation/job-id/{0}".format(jobId))
        if r.status_code != 200:
            logger.error(
                "Client {0} rejected trigger_importation request".format(client))
            raise requests.ConnectionError
        logger.info("Importation Triggered.")
    except requests.ConnectionError:
        logger.error("Unable to connect to client {0}".format(client))
        raise requests.ConnectionError
    except Exception:
        logger.error("Unexpected error occured. {0}".format(
            traceback.format_exc()))
        raise ValueError


def handle_output(player_id, line_output, client_list, jobId):
    if player_id != 0:
        return
    threads = []
    if line_output == WAIT:
        for client in client_list:
            logger.info("Connecting to client {0}....".format(client))
            thread = Thread(target=trigger_importation, args=(client, jobId))
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()


def generate_code(replacement_line_1, replacement_line_2, computationType, jobId):
    logger.info("Generating MPC code...")
    try:
        f = open(MPC_PROGRAM(computationType))
        _, _, remainder = f.readline(), f.readline(), f.read()
        if remainder == "":
            return
        t = open(MPC_PROGRAM(computationType), "w")
        t.write(replacement_line_1 + "\n" +
                replacement_line_2 + "\n" + remainder)
        f.close()
        t.close()
    except Exception:
        logger.error("Failed to generate code. Aborting: {0}".format(
            traceback.format_exc()))
        requests.post(
            coordinator + "/api/result",
            json={
                JobId: jobId,
                ComputationOutput: None
            }
        )
        abort(500)


def generate_and_compile(clients, dataset_size, computationType, jobId):
    logger.info("Starting generate and compile sequence")
    logger.info("Reported size: {0}".format(dataset_size))
    logger.info("Reported no. of clients: {0}".format(len(clients)))
    def MPC_Fi_LINE(x): return 'no_clients = {0}'.format(len(clients))
    def MPC_Se_LINE(x): return 'bins = {0}'.format(dataset_size)
    logger.info("The commandline is {}".format(
        cmd_compile_player(computationType)))
    generate_code(MPC_Fi_LINE(clients), MPC_Se_LINE(
        dataset_size), computationType, jobId)
    try:
        out = subprocess.check_output(cmd_compile_player(computationType))
    except subprocess.CalledProcessError as e:
        logger.error("Error compiling MPC program. Aborting...")
        raise ValueError


def run_smpc_computation(player_id, client_list, jobId, computationType, datasetSize):
    jobId = str(jobId)
    logger.info("Running SMPC computation, jobId {0}...".format(jobId))
    cmd_run_player = "./Player.x {0} Programs/{2} -pnb 6000 -dOT -f 1 -max {3},{3},{3} -clients {1}".format(
        player_id, len(client_list), MPC_PROGRAM_NAME(computationType), datasetSize * len(client_list))
    try:
        cmdpipe = subprocess.Popen(
            cmd_run_player, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, preexec_fn=os.setsid)
    except Exception:
        logger.error(
            "Failed to run SMPC player.x in new subprocess. Aborting...")
    computation_result = None
    logger.info(
        "[{0}] Command ran succesfully {1}. Computation in progress...".format(jobId, cmd_run_player))
    switch = False
    start = time.time()
    while True:
        if time.time() - start > 300:
            logger.error("Computation timed out")
            try:
        # Send the signal to all the process groups
                cmdpipe.terminate()
                cmdpipe.wait()
                subprocess.Popen(['reset']).wait()
                os.killpg(os.getpgid(cmdpipe.pid), signal.SIGTERM)
            except OSError:
                logger.warning("Failed to kill subprocess. Should have exited")
                logger.warning("is alive: {0}".format(cmdpipe.poll() is None))
            if cmdpipe.poll() is None:
                logger.info("terminate | wait didnt work. Trying killpg...")
                os.killpg(os.getpgid(cmdpipe.pid), signal.SIGTERM)
            break
        try:
            out = cmdpipe.stdout.readline().decode()
        except UnicodeDecodeError:
            continue
        # out_err = cmdpipe.stderr.readline().decode()
        logger.info(out)
        # logger.error(out_err)
        # print(out)
        if out == '' and cmdpipe.poll() != None:
            break
        if out != '':
            # print("Non-empty line")
            line_output = out.split("\n")[0]
            handle_output(player_id, line_output, client_list, jobId)
            if (line_output == OUTPUT_END):
                # print("OUTPUT_END was found")
                switch = False
            if (switch):
                computation_result += [str(out.split("\n")[0])]
            if (line_output == OUTPUT_START and computation_result is None):
                # print("OUTPUT_START was found")
                computation_result = []
                switch = True
            # sys.stdout.write(out)
            sys.stdout.flush()
    try:
        # Send the signal to all the process groups
        cmdpipe.terminate()
        cmdpipe.wait()
        subprocess.Popen(['reset']).wait()
        os.killpg(os.getpgid(cmdpipe.pid), signal.SIGTERM)
    except OSError:
        logger.warning("Failed to kill subprocess. Should have exited")
        logger.warning("is alive: {0}".format(cmdpipe.poll() is None))
    if cmdpipe.poll() is None:
        logger.info("terminate | wait didnt work. Trying killpg...")
        os.killpg(os.getpgid(cmdpipe.pid), signal.SIGTERM)

    logger.info("The computation result is {0}".format(computation_result))
    if computation_result is None:
        logger.error(
            "The computation failed... No further information is available at the moment. Check that all players were up and that no illegal value was specified in the data.")
    try:
        requests.post(
            coordinator + "/api/result",
            json={
                JobId: jobId,
                ComputationOutput: computation_result
            }
        )
    except requests.ConnectionError:
        logger.error("Failed to return result to coordinator.")
