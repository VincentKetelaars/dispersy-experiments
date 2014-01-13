UAV=${HOME}/svn/norut/uav/trunk

export PYTHONPATH=${PWD}:${PWD}/tribler:$UAV:.

cd $UAV
python -m Tools.ConfigTool delete version -v default
# ./deps.sh
./prepare_mysql.sh
# ./disable_uav_processes.sh
./start_uav.sh &> ~/Desktop/logs5 &
cd -

wait

grep --text "\->\|<\-" ~/Desktop/logs6 > ~/Desktop/logs4