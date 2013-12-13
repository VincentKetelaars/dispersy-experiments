database=$1
id=$2

mysql $database -e "SET @id = '${id}'; SOURCE get_children.sql;"