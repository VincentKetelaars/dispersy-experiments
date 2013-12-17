UAV=${HOME}/svn/norut/uav/trunk

export PYTHONPATH=${PWD}:${PWD}/tribler:$UAV:.

cd $UAV
# ./deps.sh
./prepare_mysql.sh
# ./disable_uav_processes.sh
./start_uav.sh &> ~/Desktop/logs5 &
cd -

wait

grep --text "\->\|<\-" ~/Desktop/logs6 > ~/Desktop/logs4