# swift=/home/vincent/git/dispersy-experiments/tribler/Tribler/SwiftEngine/swift 
swift=/home/vincent/git/dispersy-experiments/libswift/swift

${swift} -l 0.0.0.0:12345 -o "/home/vincent/Desktop/test_multi" -M "/home/vincent/Desktop/test_multi/multi" "tutorial.pdf" "test1"&>~/Desktop/logs4 &
${swift} -t 127.0.0.1:12345 -o "/home/vincent/Desktop/tests_dest_2" -h 508c23086aedfd14066baa0e840a31cc7ddd288f -w &>~/Desktop/logs5 &
# Hash: 508c23086aedfd14066baa0e840a31cc7ddd288f
sleep 10
pkill swift

# Don't forget to check if /tmp already has the file.