UAV=${HOME}/svn/norut/uav/uav/trunk

export PYTHONPATH=${PYTHONPATH}:${PWD}:${PWD}/tribler:$UAV:.

cd $UAV
# ./deps.sh
./prepare_mysql.sh
./start_uav.sh &> ~/Desktop/logs5 &
cd -

python -O -m src.uav_api -d /home/vincent/Desktop/test_large -D /home/vincent/Desktop/tests_dest -t 5 \
-l 127.0.0.1:12346 -p 127.0.0.1:12345 &> ~/Desktop/logs1 &
python -O -m src.uav_api -d /home/vincent/Desktop/tests -D /home/vincent/Desktop/tests_dest_2 -t 5 \
-l 127.0.0.1:12345 -p 127.0.0.1:12346 &> ~/Desktop/logs2 &

wait

grep --text "\->\|<\-\|CANDIDATES" ~/Desktop/logs1 > ~/Desktop/logs3
grep --text "\->\|<\-\|CANDIDATES" ~/Desktop/logs2 > ~/Desktop/logs4