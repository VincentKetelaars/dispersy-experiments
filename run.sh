export PYTHONPATH=${PYTHONPATH}:/home/vincent/git/MyDispersy

for (( PEER=1; PEER< $1 + 1 ; PEER++ )); do
    python -O src/main.py -s False &
done
wait