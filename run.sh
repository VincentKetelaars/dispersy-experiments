export PYTHONPATH=${PYTHONPATH}:${PWD}:${PWD}/tribler

python -O -m src.dispersy_instance -i -d /home/vincent/Desktop/test_large -t 6 -p 12345 &> ~/Desktop/logs1 &
python -O -m src.dispersy_instance -i -D /home/vincent/Desktop/tests_dest -t 6 -P 12345 -p 11111 &> ~/Desktop/logs2 &

wait