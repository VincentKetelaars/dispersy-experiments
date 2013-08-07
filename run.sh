export PYTHONPATH=${PYTHONPATH}:/home/vincent/git/MyDispersy

for (( PEER=1; PEER<3; PEER++ )); do
    python src/main.py &
done
wait