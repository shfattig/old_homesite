
// - - - - - - - - - - - - EXECUTION - - - - - - - - - - - - //

// Set up venv and scripts
source setup

// Run server
run

// Open previous vim session
vim -S Session.vim


// - - - - - - - - - - - - DATABASE - - - - - - - - - - - - //

// Initialize database
flask db init

// Migrate database changes (or new table)
flask db migrate -m "message"

// Apply database changes
flask db upgrade

// Revert to previous migration script
flask db downgrade

