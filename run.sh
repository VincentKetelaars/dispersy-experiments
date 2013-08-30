export PYTHONPATH=${PYTHONPATH}:${PWD}

python -O -m src.main -n $* &

wait