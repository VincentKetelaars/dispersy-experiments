# swift=/home/vincent/git/dispersy-experiments/tribler/Tribler/SwiftEngine/swift 
swift=/home/vincent/git/dispersy-experiments/libswift/swift

${swift} -l 0.0.0.0:12345 -d "/home/vincent/Desktop/test_large" &>~/Desktop/logs4 &
${swift} -t 127.0.0.1:12345 -o "/home/vincent/Desktop/tests_dest_2" -h 393bc3fcc6e6291f7a0ab9d28fbeb9a149287d0c &>~/Desktop/logs5 &
# Hash: 393bc3fcc6e6291f7a0ab9d28fbeb9a149287d0c # Picture
sleep 10
pkill swift