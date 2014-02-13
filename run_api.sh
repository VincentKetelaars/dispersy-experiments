python -O -m src.api -d /home/vincent/Desktop/test_large -D /home/vincent/Desktop/tests_dest -t 60 \
-l 193.156.108.78:12344 193.156.108.78:12345 -p 193.156.108.78:12346 -b 5 &> ~/Desktop/logs1 &
python -O -m src.api -d /home/vincent/Desktop/tests -D /home/vincent/Desktop/tests_dest_2 -t 60 \
-l 193.156.108.78:12346 193.156.108.78:12347 -b 5  &> ~/Desktop/logs2 &

#sleep 10

#python -O -m src.dispersy_instance -i -D /home/vincent/Desktop/tests_dest_2 -t 10 -P 12345 11111 -p 12121 &> ~/Desktop/logs3 &

wait

grep --text "\->\|<\-\|CANDIDATES" ~/Desktop/logs1 > ~/Desktop/logs3
grep --text "\->\|<\-\|CANDIDATES" ~/Desktop/logs2 > ~/Desktop/logs4