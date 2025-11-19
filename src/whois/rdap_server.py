#!/usr/bin/env python3
"""
QENEX RDAP Server
Registration Data Access Protocol (RFC 7483)
HTTPS-based WHOIS service
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import psycopg2
import logging
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import re

# Configuration
import os

RDAP_HOST = '0.0.0.0'
RDAP_PORT = 8080
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'qenex_whois'),
    'user': os.getenv('DB_USER', 'whois_user'),
    'password': os.getenv('DB_PASSWORD', 'whois_secure_password_2025'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432'))
}

# Logging setup
log_handlers = [logging.StreamHandler()]
log_dir = os.getenv('LOG_DIR', '/app/logs')
if os.path.exists(log_dir):
    log_handlers.append(logging.FileHandler(f'{log_dir}/rdap_server.log'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger('RDAP-Server')

class RDAPHandler(BaseHTTPRequestHandler):
    """RDAP HTTP Request Handler"""

    def __init__(self, *args, **kwargs):
        self.db_conn = None
        super().__init__(*args, **kwargs)

    def connect_db(self):
        """Connect to PostgreSQL database"""
        if not self.db_conn or self.db_conn.closed:
            try:
                self.db_conn = psycopg2.connect(**DB_CONFIG)
                return True
            except Exception as e:
                logger.error(f"Database connection failed: {e}")
                return False
        return True

    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info("%s - %s" % (self.client_address[0], format % args))

    def send_json_response(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/rdap+json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'max-age=3600')
        self.end_headers()

        json_data = json.dumps(data, indent=2)
        self.wfile.write(json_data.encode('utf-8'))

    def send_error_response(self, error_code, title, description):
        """Send RDAP error response"""
        error_data = {
            'errorCode': error_code,
            'title': title,
            'description': description,
            'rdapConformance': ['rdap_level_0']
        }
        self.send_json_response(error_data, error_code)

    def query_domain(self, domain):
        """Query domain from database"""
        try:
            if not self.connect_db():
                return None

            cursor = self.db_conn.cursor()
            query = """
                SELECT domain_name, registrar, registrar_iana_id, registrar_whois_server,
                       registrar_url, creation_date, expiration_date, updated_date,
                       status, nameservers, dnssec, abuse_email, abuse_phone
                FROM domains
                WHERE domain_name = %s
            """
            cursor.execute(query, (domain.lower(),))
            result = cursor.fetchone()
            cursor.close()

            if result:
                return {
                    'domain': result[0],
                    'registrar': result[1],
                    'iana_id': result[2],
                    'whois_server': result[3],
                    'url': result[4],
                    'created': result[5],
                    'expires': result[6],
                    'updated': result[7],
                    'status': result[8],
                    'nameservers': result[9],
                    'dnssec': result[10],
                    'abuse_email': result[11],
                    'abuse_phone': result[12]
                }
            return None

        except psycopg2.errors.UndefinedTable:
            logger.warning("domains table not found")
            return None
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return None

    def format_rdap_domain(self, domain, data):
        """Format domain data as RDAP JSON"""
        if not data:
            return None

        # Convert status array to list if it's a string
        status_list = data['status'] if isinstance(data['status'], list) else ['ok']

        # Parse nameservers
        nameservers_list = []
        if data['nameservers']:
            ns_names = data['nameservers'].split(',') if isinstance(data['nameservers'], str) else [data['nameservers']]
            nameservers_list = [
                {
                    'objectClassName': 'nameserver',
                    'ldhName': ns.strip()
                } for ns in ns_names if ns.strip()
            ]

        # Format dates
        def format_date(dt):
            if isinstance(dt, datetime):
                return dt.isoformat() + 'Z'
            return str(dt) if dt else None

        rdap_response = {
            'rdapConformance': ['rdap_level_0'],
            'objectClassName': 'domain',
            'ldhName': domain.lower(),
            'unicodeName': domain.lower(),
            'status': status_list,
            'entities': [
                {
                    'objectClassName': 'entity',
                    'handle': 'REDACTED',
                    'roles': ['registrant'],
                    'remarks': [
                        {
                            'title': 'REDACTED FOR PRIVACY',
                            'description': [
                                'Personal data has been redacted in accordance with GDPR and ICANN policies.'
                            ],
                            'type': 'object redacted due to authorization'
                        }
                    ]
                },
                {
                    'objectClassName': 'entity',
                    'roles': ['registrar'],
                    'publicIds': [
                        {
                            'type': 'IANA Registrar ID',
                            'identifier': data['iana_id'] or 'TBD'
                        }
                    ],
                    'vcardArray': [
                        'vcard',
                        [
                            ['version', {}, 'text', '4.0'],
                            ['fn', {}, 'text', data['registrar'] or 'QENEX LTD']
                        ]
                    ],
                    'entities': [
                        {
                            'objectClassName': 'entity',
                            'roles': ['abuse'],
                            'vcardArray': [
                                'vcard',
                                [
                                    ['version', {}, 'text', '4.0'],
                                    ['fn', {}, 'text', 'Abuse Contact'],
                                    ['email', {}, 'text', data['abuse_email'] or 'abuse@qenex.ai'],
                                    ['tel', {}, 'text', data['abuse_phone'] or '+44.7888867644']
                                ]
                            ]
                        }
                    ]
                }
            ],
            'events': [
                {
                    'eventAction': 'registration',
                    'eventDate': format_date(data['created'])
                },
                {
                    'eventAction': 'expiration',
                    'eventDate': format_date(data['expires'])
                },
                {
                    'eventAction': 'last changed',
                    'eventDate': format_date(data['updated'])
                }
            ],
            'nameservers': nameservers_list,
            'secureDNS': {
                'delegationSigned': data['dnssec'] == 'signed'
            },
            'notices': [
                {
                    'title': 'Terms of Use',
                    'description': [
                        'Access to WHOIS information is provided to assist in determining the '
                        'contents of a domain name registration record. QENEX LTD makes this '
                        'information available "as is" and does not guarantee its accuracy. '
                        'By submitting a WHOIS query, you agree that you will use this data '
                        'only for lawful purposes and that you will not use it to: (1) allow, '
                        'enable, or otherwise support the transmission of mass unsolicited, '
                        'commercial advertising or solicitations; (2) enable high volume, '
                        'automated processes to query and retrieve data; or (3) enable any '
                        'automated or robotic processes to collect or compile data for any purpose.'
                    ],
                    'links': [
                        {
                            'rel': 'self',
                            'href': f'https://rdap.qenex.ai/domain/{domain.lower()}',
                            'type': 'application/rdap+json'
                        }
                    ]
                },
                {
                    'title': 'Status Codes',
                    'description': [
                        'For more information on domain status codes, please visit https://icann.org/epp'
                    ]
                },
                {
                    'title': 'RDAP Terms of Service',
                    'description': [
                        'By querying our RDAP service, you agree to comply with these terms of service.'
                    ]
                },
                {
                    'title': 'Registrar Information',
                    'description': [
                        'Registrar: QENEX LTD',
                        'UK Company Number: 16523814',
                        'Address: Northway House, 257-258 Upper Street, England, N1 1RU, United Kingdom',
                        'ARIN Org-ID: QL-130',
                        'ARIN POC: ADMIN9197-ARIN',
                        'RIPE Maintainer: QENEX-MNT',
                        'Multi-RIR Operations: ARIN (Americas) + RIPE (Europe)'
                    ]
                }
            ],
            'remarks': [
                {
                    'title': 'Data Source',
                    'description': [
                        f'This data was last updated on {format_date(data["updated"])}'
                    ]
                }
            ],
            'links': [
                {
                    'value': f'https://rdap.qenex.ai/domain/{domain.lower()}',
                    'rel': 'self',
                    'href': f'https://rdap.qenex.ai/domain/{domain.lower()}',
                    'type': 'application/rdap+json'
                }
            ]
        }

        return rdap_response

    def do_GET(self):
        """Handle GET requests"""
        try:
            parsed = urlparse(self.path)
            path_parts = parsed.path.strip('/').split('/')

            # Root endpoint - Help
            if not path_parts or path_parts[0] == '':
                self.send_json_response({
                    'rdapConformance': ['rdap_level_0'],
                    'notices': [
                        {
                            'title': 'QENEX RDAP Service',
                            'description': [
                                'Welcome to QENEX LTD RDAP (Registration Data Access Protocol) service.',
                                'This service provides domain registration data in JSON format.',
                                '',
                                'Available endpoints:',
                                '  /domain/{domain-name} - Query domain information',
                                '  /help - This help information',
                                '',
                                'Example: /domain/example.com'
                            ]
                        }
                    ]
                })
                return

            # Help endpoint
            if path_parts[0] == 'help':
                self.send_json_response({
                    'rdapConformance': ['rdap_level_0'],
                    'notices': [
                        {
                            'title': 'QENEX RDAP Service',
                            'description': [
                                'RDAP endpoints:',
                                '',
                                'Domain lookup: /domain/{domain-name}',
                                'Example: https://rdap.qenex.ai/domain/example.com',
                                '',
                                'For more information about RDAP, visit:',
                                'https://www.icann.org/rdap'
                            ]
                        }
                    ]
                })
                return

            # Domain lookup
            if path_parts[0] == 'domain' and len(path_parts) >= 2:
                domain_name = path_parts[1]

                # Validate domain name
                domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
                if not re.match(domain_pattern, domain_name):
                    self.send_error_response(400, 'Bad Request', 'Invalid domain name format')
                    return

                logger.info(f"RDAP query for domain: {domain_name}")

                # Query database
                data = self.query_domain(domain_name)

                if data:
                    rdap_data = self.format_rdap_domain(domain_name, data)
                    self.send_json_response(rdap_data)
                else:
                    self.send_error_response(404, 'Not Found', f'Domain {domain_name} not found in registry')
                return

            # Unknown endpoint
            self.send_error_response(404, 'Not Found', 'The requested RDAP resource was not found')

        except Exception as e:
            logger.error(f"Request error: {e}", exc_info=True)
            self.send_error_response(500, 'Internal Server Error', 'An error occurred processing your request')

    def do_HEAD(self):
        """Handle HEAD requests"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/rdap+json')
        self.end_headers()

    def do_OPTIONS(self):
        """Handle OPTIONS requests (CORS preflight)"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def run_server():
    """Start RDAP server"""
    logger.info("="*60)
    logger.info("QENEX RDAP Server v1.0")
    logger.info("RFC 7483 Compliant - ICANN Registrar Accreditation")
    logger.info("="*60)

    server = HTTPServer((RDAP_HOST, RDAP_PORT), RDAPHandler)
    logger.info(f"RDAP Server started on http://{RDAP_HOST}:{RDAP_PORT}")
    logger.info(f"Endpoints:")
    logger.info(f"  - /domain/{{domain-name}} - Domain lookup")
    logger.info(f"  - /help - Help information")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    finally:
        server.server_close()

if __name__ == '__main__':
    run_server()
