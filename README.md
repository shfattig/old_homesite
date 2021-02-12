
// - - - - - - - - - - - - EXECUTION - - - - - - - - - - - - //

// Set up venv and scripts
source setup

// Run server
run

// Open previous vim session
vim -S Session.vim


// - - - - - - - - - - - - DATABASE - - - - - - - - - - - - //

// Migrate database changes (or new table)
flask db migrate -m "<tablename> table"

// Apply database changes
flask db upgrade

// Revert to previous migration script
flask db downgrade

