python -O -m src.tests.main_interface_api -d /home/vincent/Desktop/test_very_very_large -D /home/vincent/Desktop/tests_dest \
-t 15 -p 193.156.108.78:12346 -b 5 &> ~/Desktop/logs1 &
python -O -m src.tests.main_interface_api -d /home/vincent/Desktop/tests -D /home/vincent/Desktop/tests_dest_2 -t 15 \
-l 193.156.108.78:12346 -b 5 &> ~/Desktop/logs2 &

#sleep 10

#python -O -m src.dispersy_instance -i -D /home/vincent/Desktop/tests_dest_2 -t 10 -P 12345 11111 -p 12121 &> ~/Desktop/logs3 &

wait

grep --text "\->\|<\-" ~/Desktop/logs1 > ~/Desktop/logs3
grep --text "\->\|<\-" ~/Desktop/logs2 > ~/Desktop/logs4