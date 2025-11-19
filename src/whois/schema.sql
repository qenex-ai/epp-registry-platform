-- QENEX WHOIS Database Schema
-- RFC 3912 (WHOIS) and RFC 7483 (RDAP) Compliant

-- Domains table (synchronized from EPP)
CREATE TABLE IF NOT EXISTS domains (
    domain_id SERIAL PRIMARY KEY,
    domain_name VARCHAR(255) UNIQUE NOT NULL,
    registrar VARCHAR(255) NOT NULL,
    registrar_iana_id VARCHAR(16),
    registrar_whois_server VARCHAR(255),
    registrar_url VARCHAR(255),
    creation_date TIMESTAMP NOT NULL,
    expiration_date TIMESTAMP NOT NULL,
    updated_date TIMESTAMP DEFAULT NOW(),
    status VARCHAR(32)[] DEFAULT ARRAY['ok'],
    nameservers TEXT,
    dnssec VARCHAR(32) DEFAULT 'unsigned',
    registrant_name VARCHAR(255),
    registrant_org VARCHAR(255),
    registrant_email VARCHAR(255),
    admin_email VARCHAR(255),
    tech_email VARCHAR(255),
    abuse_email VARCHAR(255) DEFAULT 'abuse@qenex.ai',
    abuse_phone VARCHAR(64),
    last_sync TIMESTAMP DEFAULT NOW(),
    CONSTRAINT domain_name_lower CHECK (domain_name = LOWER(domain_name))
);

-- WHOIS query log (for rate limiting and abuse detection)
CREATE TABLE IF NOT EXISTS whois_queries (
    query_id SERIAL PRIMARY KEY,
    query_text VARCHAR(255) NOT NULL,
    client_ip INET NOT NULL,
    query_time TIMESTAMP DEFAULT NOW(),
    response_code VARCHAR(16) DEFAULT 'found',
    query_type VARCHAR(16) DEFAULT 'domain'
);

-- Registrar information (for registrar WHOIS lookups)
CREATE TABLE IF NOT EXISTS registrars (
    registrar_id VARCHAR(64) PRIMARY KEY,
    registrar_name VARCHAR(255) NOT NULL,
    iana_id VARCHAR(16) UNIQUE,
    whois_server VARCHAR(255),
    url VARCHAR(255),
    abuse_email VARCHAR(255),
    abuse_phone VARCHAR(64),
    address_street VARCHAR(255),
    address_city VARCHAR(128),
    address_state VARCHAR(128),
    address_postal VARCHAR(32),
    address_country CHAR(2),
    status VARCHAR(32) DEFAULT 'active',
    accreditation_date TIMESTAMP,
    CONSTRAINT registrar_status_check CHECK (status IN ('active', 'suspended', 'terminated'))
);

-- Rate limiting tracking
CREATE TABLE IF NOT EXISTS rate_limits (
    ip_address INET PRIMARY KEY,
    query_count INTEGER DEFAULT 0,
    window_start TIMESTAMP DEFAULT NOW(),
    blocked_until TIMESTAMP,
    total_queries BIGINT DEFAULT 0,
    first_seen TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW()
);

-- RDAP conformance levels
CREATE TABLE IF NOT EXISTS rdap_config (
    config_key VARCHAR(64) PRIMARY KEY,
    config_value TEXT,
    description TEXT,
    updated_date TIMESTAMP DEFAULT NOW()
);

-- Insert default RDAP configuration
INSERT INTO rdap_config (config_key, config_value, description) VALUES
    ('rdap_base_url', 'https://rdap.qenex.ai', 'Base URL for RDAP service'),
    ('conformance_level', 'rdap_level_0', 'RDAP conformance level'),
    ('max_query_rate', '100', 'Maximum queries per minute per IP'),
    ('privacy_redacted', 'true', 'Enable GDPR privacy redaction')
ON CONFLICT (config_key) DO NOTHING;

-- Insert QENEX as a registrar
INSERT INTO registrars (
    registrar_id,
    registrar_name,
    whois_server,
    url,
    abuse_email,
    abuse_phone,
    address_city,
    address_country,
    status
) VALUES (
    'qenex-ltd',
    'QENEX LTD',
    'whois.qenex.ai',
    'https://www.qenex.ai',
    'abuse@qenex.ai',
    '+44.XXXXXXXXXX',
    'London',
    'GB',
    'active'
) ON CONFLICT (registrar_id) DO NOTHING;

-- Create indexes
CREATE INDEX idx_whois_domains_name ON domains(domain_name);
CREATE INDEX idx_whois_domains_registrar ON domains(registrar);
CREATE INDEX idx_whois_domains_expiration ON domains(expiration_date);
CREATE INDEX idx_whois_queries_ip ON whois_queries(client_ip);
CREATE INDEX idx_whois_queries_time ON whois_queries(query_time DESC);
CREATE INDEX idx_rate_limits_window ON rate_limits(window_start);

-- Create view for WHOIS responses
CREATE OR REPLACE VIEW whois_domain_view AS
SELECT
    d.domain_name,
    d.registrar,
    d.registrar_iana_id,
    d.registrar_whois_server,
    d.registrar_url,
    d.creation_date,
    d.expiration_date,
    d.updated_date,
    d.status,
    d.nameservers,
    d.dnssec,
    d.abuse_email,
    d.abuse_phone,
    r.registrar_name as registrar_full_name
FROM domains d
LEFT JOIN registrars r ON d.registrar = r.registrar_id;

COMMENT ON TABLE domains IS 'Domain WHOIS data synchronized from EPP registry';
COMMENT ON TABLE whois_queries IS 'Query log for rate limiting and abuse detection';
COMMENT ON TABLE registrars IS 'ICANN-accredited registrar information';
COMMENT ON TABLE rate_limits IS 'IP-based rate limiting for WHOIS queries';
