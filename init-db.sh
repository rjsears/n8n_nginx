#!/bin/bash
# PostgreSQL initialization script
# Creates the management database and user, enables pgvector extension

set -e

# Enable pgvector extension on main n8n database
echo "Enabling pgvector extension on $POSTGRES_DB..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL
echo "pgvector extension enabled!"

# Function to create database if not exists
create_database() {
    local database=$1
    echo "Creating database: $database"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
        SELECT 'CREATE DATABASE $database'
        WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$database')\gexec
EOSQL
}

# Function to create user if not exists
create_user() {
    local username=$1
    local password=$2
    echo "Creating user: $username"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
        DO \$\$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$username') THEN
                CREATE USER $username WITH PASSWORD '$password';
            END IF;
        END
        \$\$;
EOSQL
}

# Create management database
create_database "n8n_management"

# Create management user (uses same password as main postgres user for simplicity)
# In production, you might want a separate password via MGMT_DB_PASSWORD env var
MGMT_USER="${MGMT_DB_USER:-n8n_mgmt}"
MGMT_PASS="${MGMT_DB_PASSWORD:-$POSTGRES_PASSWORD}"

create_user "$MGMT_USER" "$MGMT_PASS"

# Grant privileges
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    GRANT ALL PRIVILEGES ON DATABASE n8n_management TO $MGMT_USER;
EOSQL

# Connect to management database and set up schema permissions
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "n8n_management" <<-EOSQL
    GRANT ALL ON SCHEMA public TO $MGMT_USER;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $MGMT_USER;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $MGMT_USER;
EOSQL

echo "Database initialization complete!"
