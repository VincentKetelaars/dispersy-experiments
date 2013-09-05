export PYTHONPATH=${PYTHONPATH}:${PWD}:${PWD}/tribler

python -O -m src.main $* &

wait