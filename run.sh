export PYTHONPATH=${PYTHONPATH}:${PWD}:${PWD}/tribler

python -O -m src.dispersy_instance -d /home/vincent/Desktop/test_large -D /home/vincent/Desktop/tests_dest -t 10 -p 12345 -P 11111 &> ~/Desktop/logs1 &
python -O -m src.dispersy_instance -d /home/vincent/Desktop/tests -D /home/vincent/Desktop/tests_dest -t 10 -p 11111  &> ~/Desktop/logs2 &

#sleep 10

#python -O -m src.dispersy_instance -i -D /home/vincent/Desktop/tests_dest_2 -t 10 -P 12345 11111 -p 12121 &> ~/Desktop/logs3 &

wait

grep "\->\|<\-\|CANDIDATES" ~/Desktop/logs1 > ~/Desktop/logs3
grep "\->\|<\-\|CANDIDATES" ~/Desktop/logs2 > ~/Desktop/logs4