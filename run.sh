export PYTHONPATH=${PYTHONPATH}:/home/vincent/git/dispersy-experiments/

python -O -m src.main -n $* &

wait