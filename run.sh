export PYTHONPATH=${PYTHONPATH}:${PWD}:${PWD}/tribler

python -O -m src.dispersy_instance -d /home/vincent/Desktop/test_large -D /home/vincent/Desktop/tests_dest -t 60 \
-l  12345 -W &> ~/Desktop/logs1 &
# python -O -m src.dispersy_instance -d /home/vincent/Desktop/tests -D /home/vincent/Desktop/tests_dest_2 -t 15 -l 192.168.0.1:11111  &> ~/Desktop/logs2 &

#sleep 10

#python -O -m src.dispersy_instance -i -D /home/vincent/Desktop/tests_dest_2 -t 10 -P 12345 11111 -p 12121 &> ~/Desktop/logs3 &

wait

grep --text "\->\|<\-\|CANDIDATES" ~/Desktop/logs1 > ~/Desktop/logs3
grep --text "\->\|<\-\|CANDIDATES" ~/Desktop/logs2 > ~/Desktop/logs4