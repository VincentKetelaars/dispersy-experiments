# swift=/home/vincent/git/dispersy-experiments/tribler/Tribler/SwiftEngine/swift 
swift=/home/vincent/git/dispersy-experiments/libswift/swift

${swift} -l 193.156.108.78:12345 -f "/home/vincent/Desktop/test_large/tutorial.pdf" &>~/Desktop/logs4 &
${swift} -t 193.156.108.78:12345 -o "/home/vincent/Desktop/tests_dest_2" -h 563c9a43aef2a25f78c74071c5df4b36e0354f76 &>~/Desktop/logs5 &
# Hash: 563c9a43aef2a25f78c74071c5df4b36e0354f76
sleep 10
# pkill swift