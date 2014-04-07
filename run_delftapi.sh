
python -m src.database.ConfigTool delete version -v default
./prepare_mysql.sh # We want to make sure we have the latest configuration

python -m src.delft_api &> $HOME/Desktop/logs5