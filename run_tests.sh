export PYTHONPATH=${PYTHONPATH}:${PWD}:${PWD}/tribler

python -m src.tests.unit.test_filepusher

wait