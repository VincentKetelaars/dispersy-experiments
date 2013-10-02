libswift/swift -l 127.0.0.1:12345 -f "/home/vincent/Desktop/test_very_large/Coupling - [2x01] - The Man with Two Legs.mkv" &>~/Desktop/logs4 &
libswift/swift -t 127.0.0.1:12345 -g 0.0.0.0:8080 -w &>~/Desktop/logs5 &
firefox http://127.0.0.1:8080/2a7ce792592e2c0aa9f3bb0ce71de80b4cc00c56
# Hash: 2a7ce792592e2c0aa9f3bb0ce71de80b4cc00c56
# sleep 10
# pkill swift