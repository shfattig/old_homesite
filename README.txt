
// - - - - - - - - - - - - EXECUTION - - - - - - - - - - - - //

// Set up venv and scripts
source setup

// Run server
run

// Open previous vim session
vim -S Session.vim


// - - - - - - - - - - - - DATABASE - - - - - - - - - - - - //

// Setup Headache //
// After installing mysql-server...

// Unset root password
>> sudo mysqld_safe --skip-grant-tables
>> mysql -u root
>> UPDATE mysql.user SET authentication_string=null WHERE User='root';
>> update user set plugin="mysql_native_password" where User='root';
>> FLUSH PRIVILEGES;
>> exit;
>> //maybe restart server?

// Set new password
>> mysql -u root
>> ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY 'yourpasswd';
    root : {pwd}

// Try logging in!
>> sudo /etc/init.d/mysql stop 
>> sudo /etc/init.d/mysql start # reset mysql
>> mysql -u root -p


// Create New User //
>> CREATE USER 'newuser'@'localhost' IDENTIFIED BY 'password';
    shaun : {pwd}
>> GRANT ALL PRIVILEGES ON * . * TO 'newuser'@'localhost'; // grant all privileges for user
>> FLUSH PRIVILEGES;


// Create Homesite Database //
>> CREATE DATABASE homesite

                ---------------------------------------------

// Initialize database
flask db init

// Migrate database changes (or new table)
flask db migrate -m "message"

// Apply database changes
flask db upgrade

// Revert to previous migration script
flask db downgrade

