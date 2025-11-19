-- QENEX EPP Database Schema
-- RFC 5730-5734 Compliant EPP Data Model

-- Sessions table
CREATE TABLE IF NOT EXISTS epp_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    client_id VARCHAR(64) NOT NULL,
    client_ip INET NOT NULL,
    login_time TIMESTAMP NOT NULL DEFAULT NOW(),
    last_activity TIMESTAMP NOT NULL DEFAULT NOW(),
    authenticated BOOLEAN DEFAULT FALSE,
    CONSTRAINT session_client_idx UNIQUE (client_id, session_id)
);

-- Clients (registrars) table
CREATE TABLE IF NOT EXISTS epp_clients (
    client_id VARCHAR(64) PRIMARY KEY,
    client_name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    status VARCHAR(32) DEFAULT 'active',
    created_date TIMESTAMP DEFAULT NOW(),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(64),
    ip_whitelist TEXT[],
    CONSTRAINT client_status_check CHECK (status IN ('active', 'suspended', 'terminated'))
);

-- Domains table
CREATE TABLE IF NOT EXISTS domains (
    domain_id SERIAL PRIMARY KEY,
    domain_name VARCHAR(255) UNIQUE NOT NULL,
    registrar_id VARCHAR(64) REFERENCES epp_clients(client_id),
    creation_date TIMESTAMP DEFAULT NOW(),
    expiration_date TIMESTAMP NOT NULL,
    last_update TIMESTAMP DEFAULT NOW(),
    status VARCHAR(32)[] DEFAULT ARRAY['ok'],
    auth_code VARCHAR(64),
    registrant_id INTEGER,
    admin_contact_id INTEGER,
    tech_contact_id INTEGER,
    billing_contact_id INTEGER,
    CONSTRAINT domain_name_lower CHECK (domain_name = LOWER(domain_name))
);

-- Nameservers table
CREATE TABLE IF NOT EXISTS nameservers (
    nameserver_id SERIAL PRIMARY KEY,
    hostname VARCHAR(255) UNIQUE NOT NULL,
    ipv4_addresses INET[],
    ipv6_addresses INET[],
    status VARCHAR(32) DEFAULT 'ok',
    created_date TIMESTAMP DEFAULT NOW(),
    CONSTRAINT hostname_lower CHECK (hostname = LOWER(hostname))
);

-- Domain-Nameserver mapping
CREATE TABLE IF NOT EXISTS domain_nameservers (
    domain_id INTEGER REFERENCES domains(domain_id) ON DELETE CASCADE,
    nameserver_id INTEGER REFERENCES nameservers(nameserver_id) ON DELETE CASCADE,
    created_date TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (domain_id, nameserver_id)
);

-- Contacts table
CREATE TABLE IF NOT EXISTS contacts (
    contact_id SERIAL PRIMARY KEY,
    contact_handle VARCHAR(64) UNIQUE NOT NULL,
    registrar_id VARCHAR(64) REFERENCES epp_clients(client_id),
    name VARCHAR(255),
    organization VARCHAR(255),
    street1 VARCHAR(255),
    street2 VARCHAR(255),
    street3 VARCHAR(255),
    city VARCHAR(128),
    state_province VARCHAR(128),
    postal_code VARCHAR(32),
    country_code CHAR(2),
    phone VARCHAR(32),
    phone_ext VARCHAR(16),
    fax VARCHAR(32),
    fax_ext VARCHAR(16),
    email VARCHAR(255),
    auth_code VARCHAR(64),
    status VARCHAR(32)[] DEFAULT ARRAY['ok'],
    created_date TIMESTAMP DEFAULT NOW(),
    last_update TIMESTAMP DEFAULT NOW(),
    disclose_flags JSONB DEFAULT '{}'::jsonb
);

-- EPP transactions log
CREATE TABLE IF NOT EXISTS epp_transactions (
    transaction_id SERIAL PRIMARY KEY,
    client_id VARCHAR(64) REFERENCES epp_clients(client_id),
    session_id VARCHAR(64),
    command_type VARCHAR(32) NOT NULL,
    object_type VARCHAR(32),
    object_id VARCHAR(255),
    request_xml TEXT,
    response_xml TEXT,
    response_code INTEGER,
    client_ip INET,
    server_transaction_id VARCHAR(64) UNIQUE,
    client_transaction_id VARCHAR(64),
    timestamp TIMESTAMP DEFAULT NOW(),
    execution_time_ms INTEGER
);

-- DNSSEC data
CREATE TABLE IF NOT EXISTS domain_dnssec (
    dnssec_id SERIAL PRIMARY KEY,
    domain_id INTEGER REFERENCES domains(domain_id) ON DELETE CASCADE,
    key_tag INTEGER NOT NULL,
    algorithm INTEGER NOT NULL,
    digest_type INTEGER NOT NULL,
    digest TEXT NOT NULL,
    created_date TIMESTAMP DEFAULT NOW(),
    CONSTRAINT dnssec_unique UNIQUE (domain_id, key_tag, algorithm, digest_type)
);

-- Transfer history
CREATE TABLE IF NOT EXISTS transfers (
    transfer_id SERIAL PRIMARY KEY,
    domain_id INTEGER REFERENCES domains(domain_id),
    old_registrar VARCHAR(64) REFERENCES epp_clients(client_id),
    new_registrar VARCHAR(64) REFERENCES epp_clients(client_id),
    transfer_status VARCHAR(32) NOT NULL,
    request_date TIMESTAMP DEFAULT NOW(),
    auth_code VARCHAR(64),
    completion_date TIMESTAMP,
    CONSTRAINT transfer_status_check CHECK (transfer_status IN
        ('pending', 'approved', 'rejected', 'cancelled', 'clientApproved', 'serverApproved'))
);

-- Create indexes for performance
CREATE INDEX idx_domains_registrar ON domains(registrar_id);
CREATE INDEX idx_domains_status ON domains USING GIN(status);
CREATE INDEX idx_domains_expiration ON domains(expiration_date);
CREATE INDEX idx_contacts_registrar ON contacts(registrar_id);
CREATE INDEX idx_transactions_client ON epp_transactions(client_id);
CREATE INDEX idx_transactions_timestamp ON epp_transactions(timestamp DESC);
CREATE INDEX idx_sessions_client ON epp_sessions(client_id);
CREATE INDEX idx_sessions_activity ON epp_sessions(last_activity);

-- Insert test client for development
INSERT INTO epp_clients (client_id, client_name, password_hash, contact_email)
VALUES (
    'test-registrar',
    'Test Registrar Account',
    '$2b$12$KIXqFw7qLvN8Y3Z8xX8xX8xX8xX8xX8xX8xX8xX8xX8xX8xX8xX8x',  -- password: testpass123
    'test@qenex.ai'
) ON CONFLICT (client_id) DO NOTHING;

COMMENT ON TABLE domains IS 'Domain name registry - RFC 5731';
COMMENT ON TABLE contacts IS 'Contact objects - RFC 5733';
COMMENT ON TABLE nameservers IS 'Host objects - RFC 5732';
COMMENT ON TABLE epp_transactions IS 'EPP command audit log';
