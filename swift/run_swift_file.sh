# swift=/home/vincent/git/libswift/swift 
# swift=/home/vincent/git/dispersy-experiments/libswift/swift
# swift=/home/vincent/git/tribler/Tribler/SwiftEngine/swift
swift=/usr/share/tribler/swift

${swift} -t 127.0.0.1:12345 -o "/home/vincent/Desktop/tests_dest_2" -B -h 563c9a43aef2a25f78c74071c5df4b36e0354f76 &>~/Desktop/logs5 &
${swift} -l 127.0.0.1:12345 -f "/home/vincent/Desktop/test_large/tutorial.pdf" -B &>~/Desktop/logs4 &
# Hash: 563c9a43aef2a25f78c74071c5df4b36e0354f76
sleep 10
pkill swift