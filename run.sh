export PYTHONPATH=${PYTHONPATH}:${PWD}:${PWD}/tribler

python -O -m src.dispersy_instance -d /home/vincent/Desktop/test_large -t 12 -p 12345 12346 &> ~/Desktop/logs1 &
python -O -m src.dispersy_instance -D /home/vincent/Desktop/tests_dest -t 12 -P 12345 12346 -p 11111 11112 &> ~/Desktop/logs2 &

#sleep 10

#python -O -m src.dispersy_instance -i -D /home/vincent/Desktop/tests_dest_2 -t 10 -P 12345 11111 -p 12121 &> ~/Desktop/logs3 &

wait