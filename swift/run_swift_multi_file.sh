# swift=/home/vincent/git/dispersy-experiments/tribler/Tribler/SwiftEngine/swift 
swift=/home/vincent/git/dispersy-experiments/libswift/swift

${swift} -l 0.0.0.0:12345 -o "/home/vincent/Desktop/test_multi" -M "/home/vincent/Desktop/test_multi/multi" \
	"tutorial.pdf" "test1"&>~/Desktop/logs4 &
${swift} -t 127.0.0.1:12345 -o "/home/vincent/Desktop/tests_dest_2" -h 884920858ed5c55d4db943a76c43cbd65ac1554f -w &>~/Desktop/logs5 &
# Hash: 884920858ed5c55d4db943a76c43cbd65ac1554f
sleep 10
pkill swift

# Don't forget to check if /tmp already has the file.