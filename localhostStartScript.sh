bash -c "python python_web/client.py 0" & 
bash -c "python python_web/client.py 1" & 
bash -c "python python_web/client.py 2" &
bash -c "python python_web/player.py 0" & 
bash -c "python python_web/player.py 1" & 
bash -c "python python_web/player.py 2" &
bash -c "python python_web/coordinator.py"