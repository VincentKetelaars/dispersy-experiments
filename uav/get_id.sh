database=$1
name=$2

mysql $database -e "SET @name = '${name}'; SOURCE get_id.sql;"