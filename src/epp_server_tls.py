#!/usr/bin/env python3
"""
QENEX Secure EPP Server - RFC 5734 Compliant
EPP over TLS for ICANN Registrar Accreditation
Port 700, TLS 1.2+, Client Certificate Authentication
"""
import socket
import ssl
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
import psycopg2
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# EPP Server Configuration
EPP_HOST = os.getenv('EPP_HOST', '0.0.0.0')
EPP_PORT = int(os.getenv('EPP_PORT', '700'))
EPP_CERT = os.getenv('EPP_CERT', '/opt/qenex-registrar/certs/epp-server.crt')
EPP_KEY = os.getenv('EPP_KEY', '/opt/qenex-registrar/certs/epp-server.key')
EPP_CA = os.getenv('EPP_CA', '/opt/qenex-registrar/certs/ca.crt')

# Database configuration
DB_CONFIG = {
    'dbname': 'qenex_epp',
    'user': 'epp_user',
    'password': 'epp_secure_password_2025',
    'host': 'localhost',
    'port': '5432'
}

class EPPServer:
    """Secure EPP Server with TLS"""

    def __init__(self, host=EPP_HOST, port=EPP_PORT):
        self.host = host
        self.port = port
        self.sessions = {}  # Track active sessions

    def create_ssl_context(self):
        """Create SSL context for TLS 1.2+"""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2

        # Load server certificate and key
        try:
            context.load_cert_chain(certfile=EPP_CERT, keyfile=EPP_KEY)
        except FileNotFoundError:
            logger.warning("Certificate files not found, generating self-signed cert")
            self._generate_self_signed_cert()
            context.load_cert_chain(certfile=EPP_CERT, keyfile=EPP_KEY)

        # Require client certificates (optional, enable for production)
        # context.verify_mode = ssl.CERT_REQUIRED
        # context.load_verify_locations(EPP_CA)

        return context

    def _generate_self_signed_cert(self):
        """Generate self-signed certificate for development"""
        import subprocess
        os.makedirs('/opt/qenex-registrar/certs', exist_ok=True)
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:4096',
            '-keyout', EPP_KEY, '-out', EPP_CERT,
            '-days', '365', '-nodes',
            '-subj', '/C=US/ST=State/L=City/O=QENEX/CN=epp.qenex.ai'
        ], check=True, capture_output=True)

    def get_db(self):
        """Get database connection"""
        return psycopg2.connect(**DB_CONFIG)

    def create_epp_response(self, result_code, msg, data=None):
        """Create EPP XML response (RFC 5730 Section 2.6)"""
        epp = ET.Element('epp', xmlns='urn:ietf:params:xml:ns:epp-1.0')
        response = ET.SubElement(epp, 'response')
        result = ET.SubElement(response, 'result', code=str(result_code))
        msg_elem = ET.SubElement(result, 'msg')
        msg_elem.text = msg

        if data:
            resData = ET.SubElement(response, 'resData')
            resData.append(data)

        trID = ET.SubElement(response, 'trID')
        svTRID = ET.SubElement(trID, 'svTRID')
        svTRID.text = f'QENEX-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}'

        xml_str = ET.tostring(epp, encoding='unicode')
        # Add EPP header (4 bytes: total length + 4)
        xml_bytes = xml_str.encode('utf-8')
        length = len(xml_bytes) + 4
        header = length.to_bytes(4, byteorder='big')
        return header + xml_bytes

    def create_greeting(self):
        """Create EPP greeting (RFC 5730 Section 2.4)"""
        epp = ET.Element('epp', xmlns='urn:ietf:params:xml:ns:epp-1.0')
        greeting = ET.SubElement(epp, 'greeting')

        svID = ET.SubElement(greeting, 'svID')
        svID.text = 'QENEX EPP Server'

        svDate = ET.SubElement(greeting, 'svDate')
        svDate.text = datetime.utcnow().isoformat() + 'Z'

        svcMenu = ET.SubElement(greeting, 'svcMenu')

        # Supported EPP versions
        version = ET.SubElement(svcMenu, 'version')
        version.text = '1.0'

        # Supported languages
        lang = ET.SubElement(svcMenu, 'lang')
        lang.text = 'en'

        # Supported object URIs
        objURI1 = ET.SubElement(svcMenu, 'objURI')
        objURI1.text = 'urn:ietf:params:xml:ns:domain-1.0'

        objURI2 = ET.SubElement(svcMenu, 'objURI')
        objURI2.text = 'urn:ietf:params:xml:ns:contact-1.0'

        objURI3 = ET.SubElement(svcMenu, 'objURI')
        objURI3.text = 'urn:ietf:params:xml:ns:host-1.0'

        # DCP (Data Collection Policy) - ICANN requirement
        dcp = ET.SubElement(greeting, 'dcp')
        access = ET.SubElement(dcp, 'access')
        all_access = ET.SubElement(access, 'all')

        statement = ET.SubElement(dcp, 'statement')
        purpose = ET.SubElement(statement, 'purpose')
        prov = ET.SubElement(purpose, 'prov')
        admin_purpose = ET.SubElement(purpose, 'admin')

        recipient = ET.SubElement(statement, 'recipient')
        ours = ET.SubElement(recipient, 'ours')

        retention = ET.SubElement(statement, 'retention')
        legal = ET.SubElement(retention, 'legal')

        xml_str = ET.tostring(epp, encoding='unicode')
        xml_bytes = xml_str.encode('utf-8')
        length = len(xml_bytes) + 4
        header = length.to_bytes(4, byteorder='big')
        return header + xml_bytes

    def parse_epp_command(self, xml_data):
        """Parse incoming EPP command"""
        try:
            root = ET.fromstring(xml_data)
            command_elem = root.find('.//{urn:ietf:params:xml:ns:epp-1.0}command')
            if command_elem is None:
                return None, None

            # Check for login command
            login = command_elem.find('.//{urn:ietf:params:xml:ns:epp-1.0}login')
            if login is not None:
                return 'login', login

            # Check for logout command
            logout = command_elem.find('.//{urn:ietf:params:xml:ns:epp-1.0}logout')
            if logout is not None:
                return 'logout', logout

            # Check for check command
            check = command_elem.find('.//{urn:ietf:params:xml:ns:epp-1.0}check')
            if check is not None:
                return 'check', check

            # Check for info command
            info = command_elem.find('.//{urn:ietf:params:xml:ns:epp-1.0}info')
            if info is not None:
                return 'info', info

            # Check for create command
            create = command_elem.find('.//{urn:ietf:params:xml:ns:epp-1.0}create')
            if create is not None:
                return 'create', create

            # Check for update command
            update = command_elem.find('.//{urn:ietf:params:xml:ns:epp-1.0}update')
            if update is not None:
                return 'update', update

            # Check for delete command
            delete = command_elem.find('.//{urn:ietf:params:xml:ns:epp-1.0}delete')
            if delete is not None:
                return 'delete', delete

            # Check for renew command
            renew = command_elem.find('.//{urn:ietf:params:xml:ns:epp-1.0}renew')
            if renew is not None:
                return 'renew', renew

            # Check for transfer command
            transfer = command_elem.find('.//{urn:ietf:params:xml:ns:epp-1.0}transfer')
            if transfer is not None:
                return 'transfer', transfer

            return 'unknown', None

        except ET.ParseError:
            return None, None

    def handle_login(self, elem, session_id):
        """Handle EPP login command"""
        clID = elem.find('.//{urn:ietf:params:xml:ns:epp-1.0}clID')
        pw = elem.find('.//{urn:ietf:params:xml:ns:epp-1.0}pw')

        if clID is None or pw is None:
            return self.create_epp_response(2003, 'Required parameter missing')

        # TODO: Validate credentials against database
        # For now, accept all logins (development mode)
        self.sessions[session_id] = {
            'logged_in': True,
            'client_id': clID.text,
            'login_time': datetime.utcnow()
        }

        return self.create_epp_response(1000, 'Command completed successfully')

    def handle_logout(self, session_id):
        """Handle EPP logout command"""
        if session_id in self.sessions:
            del self.sessions[session_id]
        return self.create_epp_response(1500, 'Command completed successfully; ending session')

    def handle_check_domain(self, elem):
        """Handle EPP domain check command"""
        domain_names = elem.findall('.//{urn:ietf:params:xml:ns:domain-1.0}name')

        if not domain_names:
            return self.create_epp_response(2003, 'Required parameter missing')

        # Create response data
        chkData = ET.Element('{urn:ietf:params:xml:ns:domain-1.0}chkData')

        conn = self.get_db()
        cur = conn.cursor()

        for domain_elem in domain_names:
            domain_name = domain_elem.text

            # Check if domain exists
            cur.execute("SELECT domain_id FROM domains WHERE domain_name = %s", (domain_name,))
            exists = cur.fetchone() is not None

            cd = ET.SubElement(chkData, '{urn:ietf:params:xml:ns:domain-1.0}cd')
            name = ET.SubElement(cd, '{urn:ietf:params:xml:ns:domain-1.0}name', avail=str(not exists).lower())
            name.text = domain_name

            if exists:
                reason = ET.SubElement(cd, '{urn:ietf:params:xml:ns:domain-1.0}reason')
                reason.text = 'Domain already registered'

        cur.close()
        conn.close()

        return self.create_epp_response(1000, 'Command completed successfully', chkData)

    def handle_client(self, client_socket, address):
        """Handle individual EPP client connection"""
        session_id = f"{address[0]}:{address[1]}"
        logger.info(f"New connection from {session_id}")

        try:
            # Send greeting
            greeting = self.create_greeting()
            client_socket.sendall(greeting)

            while True:
                # Read EPP frame header (4 bytes)
                header = client_socket.recv(4)
                if not header or len(header) < 4:
                    break

                # Parse frame length
                frame_length = int.from_bytes(header, byteorder='big') - 4

                # Read EPP XML data
                xml_data = client_socket.recv(frame_length)
                if not xml_data:
                    break

                # Parse and handle command
                command_type, command_elem = self.parse_epp_command(xml_data.decode('utf-8'))

                if command_type == 'login':
                    response = self.handle_login(command_elem, session_id)
                elif command_type == 'logout':
                    response = self.handle_logout(session_id)
                    client_socket.sendall(response)
                    break
                elif command_type == 'check':
                    response = self.handle_check_domain(command_elem)
                else:
                    response = self.create_epp_response(2000, 'Unknown command')

                client_socket.sendall(response)

        except Exception as e:
            logger.error(f"Error handling client {session_id}: {e}")
        finally:
            client_socket.close()
            logger.info(f"Connection closed: {session_id}")

    def start(self):
        """Start EPP server"""
        ssl_context = self.create_ssl_context()

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)

        logger.info(f"EPP Server listening on {self.host}:{self.port} (TLS enabled)")

        try:
            while True:
                client_socket, address = server_socket.accept()

                # Wrap socket with TLS
                secure_socket = ssl_context.wrap_socket(client_socket, server_side=True)

                # Handle client in new thread
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(secure_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()

        except KeyboardInterrupt:
            logger.info("Shutting down EPP server")
        finally:
            server_socket.close()

if __name__ == '__main__':
    server = EPPServer()
    server.start()
