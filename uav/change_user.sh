# ./Tools/FlightDatabaseServer 19
# ./Tools/ManageData 47
# ./clean-payload-data.sh often
# ./Common/Config.py 165
# ./create_db.sql 2
# ./Config/defaultConfiguration.xml often
# ./root/install.sh 12
# ./dump_data_from_plane.sh 28, 60

OLD_USER=$1
USER=$2
PASSWORD=$3
PASSWORD_REGEX="[a-zA-Z0-9]*"

# Capture the part before the username and copy that, replace the username 
sed -i "s/\(dbUser=\"\)$OLD_USER\"/\1$USER\"/g" ./Tools/FlightDatabaseServer.py
sed -i "s/$OLD_USER -p$PASSWORD_REGEX/$USER -p$PASSWORD/g" ./clean-payload-data.sh
sed -i "s/$OLD_USER/$USER/g" ./Common/Config.py
sed -i "s/$OLD_USER/$USER/g" ./create_db.sql
sed -i "s/$OLD_USER/$USER/g" ./Config/defaultConfiguration_vincent.xml
sed -i "s/$OLD_USER/$USER/g" ./root/install.sh
sed -i "s/$OLD_USER/$USER/g" ./dump_data_from_plane.sh

# Capture the part before the password and copy that, replace the password 
sed -i "s/\(dbPasswd=\"\)$PASSWORD_REGEX\"/\1$PASSWORD\"/g" ./Tools/FlightDatabaseServer.py 
sed -i "s/\(\"db_password\": \"\)$PASSWORD_REGEX\"/\1$PASSWORD\"/g" ./Common/Config.py
sed -i "s/by '$PASSWORD_REGEX'/by '$PASSWORD'/g" ./create_db.sql 
sed -i "s/\(<db_password>\)$PASSWORD_REGEX/\1$PASSWORD/g" ./Config/defaultConfiguration_vincent.xml