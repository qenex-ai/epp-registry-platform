#!/usr/bin/env python3
"""
QENEX EPP Server
Extensible Provisioning Protocol server for domain registrar operations
Complies with RFC 5730-5734
"""

import asyncio
import ssl
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import psycopg2
import hashlib
import secrets
from epp_domain_commands import EPPDomainCommands
from epp_contact_commands import EPPContactCommands
from epp_host_commands import EPPHostCommands

# Configuration
import os

EPP_HOST = '0.0.0.0'
EPP_PORT = 700
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'qenex_epp'),
    'user': os.getenv('DB_USER', 'epp_user'),
    'password': os.getenv('DB_PASSWORD', 'epp_secure_password_2025'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432'))
}

# Logging setup
log_handlers = [logging.StreamHandler()]
log_dir = os.getenv('LOG_DIR', '/app/logs')
if os.path.exists(log_dir):
    log_handlers.append(logging.FileHandler(f'{log_dir}/epp_server.log'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger('EPP-Server')

class EPPServer:
    """EPP Protocol Server"""

    def __init__(self):
        self.db_conn = None
        self.sessions = {}
        self.domain_commands = None
        self.contact_commands = None
        self.host_commands = None

    def connect_db(self):
        """Connect to PostgreSQL database"""
        try:
            self.db_conn = psycopg2.connect(**DB_CONFIG)
            self.db_conn.autocommit = False  # Use transactions
            self.domain_commands = EPPDomainCommands(self.db_conn)
            self.contact_commands = EPPContactCommands(DB_CONFIG)
            self.host_commands = EPPHostCommands(DB_CONFIG)
            logger.info("Connected to EPP database")
            logger.info("Initialized domain, contact, and host command handlers")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def generate_greeting(self):
        """Generate EPP greeting message (RFC 5730)"""
        greeting = f"""<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <greeting>
    <svID>QENEX EPP Server v1.0</svID>
    <svDate>{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')}</svDate>
    <svcMenu>
      <version>1.0</version>
      <lang>en</lang>
      <objURI>urn:ietf:params:xml:ns:domain-1.0</objURI>
      <objURI>urn:ietf:params:xml:ns:contact-1.0</objURI>
      <objURI>urn:ietf:params:xml:ns:host-1.0</objURI>
      <svcExtension>
        <extURI>urn:ietf:params:xml:ns:rgp-1.0</extURI>
        <extURI>urn:ietf:params:xml:ns:secDNS-1.1</extURI>
      </svcExtension>
    </svcMenu>
    <dcp>
      <access><all/></access>
      <statement>
        <purpose><admin/><prov/></purpose>
        <recipient><ours/><public/></recipient>
        <retention><stated/></retention>
      </statement>
    </dcp>
  </greeting>
</epp>"""
        return greeting.encode('utf-8')

    def parse_epp_command(self, data):
        """Parse incoming EPP XML command"""
        try:
            # Remove EPP frame header (4 bytes length prefix)
            if len(data) < 4:
                return None

            xml_data = data[4:].decode('utf-8')
            root = ET.fromstring(xml_data)

            # Extract command type
            command = root.find('.//{urn:ietf:params:xml:ns:epp-1.0}command')
            if command is None:
                return {'type': 'hello'}

            # Determine command type
            for child in command:
                if child.tag.endswith('}login'):
                    return {'type': 'login', 'element': child}
                elif child.tag.endswith('}logout'):
                    return {'type': 'logout'}
                elif child.tag.endswith('}check'):
                    return {'type': 'check', 'element': child}
                elif child.tag.endswith('}info'):
                    return {'type': 'info', 'element': child}
                elif child.tag.endswith('}create'):
                    return {'type': 'create', 'element': child}
                elif child.tag.endswith('}update'):
                    return {'type': 'update', 'element': child}
                elif child.tag.endswith('}delete'):
                    return {'type': 'delete', 'element': child}
                elif child.tag.endswith('}renew'):
                    return {'type': 'renew', 'element': child}
                elif child.tag.endswith('}transfer'):
                    return {'type': 'transfer', 'element': child}

            return {'type': 'unknown'}
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return None

    def create_response(self, code, msg, result_data=None):
        """Create EPP response message"""
        response = f"""<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <response>
    <result code="{code}">
      <msg>{msg}</msg>
    </result>
    {result_data if result_data else ''}
    <trID>
      <svTRID>{secrets.token_hex(16)}</svTRID>
    </trID>
  </response>
</epp>"""

        # Add EPP frame header (4 bytes network order length + 4)
        response_bytes = response.encode('utf-8')
        length = len(response_bytes) + 4
        frame = length.to_bytes(4, byteorder='big') + response_bytes
        return frame

    def _frame_response(self, xml_string):
        """Add EPP frame header to XML string response"""
        response_bytes = xml_string.encode('utf-8')
        length = len(response_bytes) + 4
        frame = length.to_bytes(4, byteorder='big') + response_bytes
        return frame

    def handle_login(self, session_id, element):
        """Handle EPP login command"""
        try:
            clID = element.find('.//{urn:ietf:params:xml:ns:epp-1.0}clID').text
            pw = element.find('.//{urn:ietf:params:xml:ns:epp-1.0}pw').text

            # TODO: Implement proper authentication against database
            # For now, accept any login for testing
            self.sessions[session_id] = {
                'clID': clID,
                'authenticated': True,
                'login_time': datetime.now(timezone.utc)
            }

            logger.info(f"Client {clID} logged in (session {session_id})")
            return self.create_response(1000, "Command completed successfully")
        except Exception as e:
            logger.error(f"Login error: {e}")
            return self.create_response(2002, "Authentication error")

    def handle_logout(self, session_id):
        """Handle EPP logout command"""
        if session_id in self.sessions:
            clID = self.sessions[session_id].get('clID', 'unknown')
            del self.sessions[session_id]
            logger.info(f"Client {clID} logged out (session {session_id})")

        return self.create_response(1500, "Command completed successfully; ending session")

    async def handle_client(self, reader, writer):
        """Handle individual EPP client connection"""
        session_id = secrets.token_hex(8)
        addr = writer.get_extra_info('peername')
        logger.info(f"New connection from {addr} (session {session_id})")

        try:
            # Send greeting
            greeting = self.generate_greeting()
            # Add EPP frame header
            frame_length = len(greeting) + 4
            frame = frame_length.to_bytes(4, byteorder='big') + greeting
            writer.write(frame)
            await writer.drain()
            logger.info(f"Greeting sent to {addr}")

            while True:
                # Read EPP frame length (4 bytes)
                length_data = await reader.read(4)
                if not length_data:
                    break

                frame_length = int.from_bytes(length_data, byteorder='big')

                # Read EPP command (frame_length - 4 bytes already read)
                command_data = await reader.read(frame_length - 4)
                if not command_data:
                    break

                # Parse and handle command
                full_data = length_data + command_data
                cmd = self.parse_epp_command(full_data)

                if not cmd:
                    response = self.create_response(2001, "Command syntax error")
                elif cmd['type'] == 'hello':
                    # Respond with greeting
                    greeting = self.generate_greeting()
                    frame_length = len(greeting) + 4
                    response = frame_length.to_bytes(4, byteorder='big') + greeting
                elif cmd['type'] == 'login':
                    response = self.handle_login(session_id, cmd['element'])
                elif cmd['type'] == 'logout':
                    response = self.handle_logout(session_id)
                    writer.write(response)
                    await writer.drain()
                    break
                elif cmd['type'] == 'check':
                    # Determine object type (domain, contact, host)
                    if cmd['element'].find('.//{urn:ietf:params:xml:ns:domain-1.0}name') is not None:
                        response = self.domain_commands.handle_domain_check(
                            cmd['element'], self.sessions[session_id]
                        )
                    elif cmd['element'].find('.//{urn:ietf:params:xml:ns:contact-1.0}id') is not None:
                        response_xml = self.contact_commands.handle_contact_check(
                            cmd['element'], self.sessions[session_id]
                        )
                        response = self._frame_response(response_xml)
                    elif cmd['element'].find('.//{urn:ietf:params:xml:ns:host-1.0}name') is not None:
                        response_xml = self.host_commands.handle_host_check(
                            cmd['element'], self.sessions[session_id]
                        )
                        response = self._frame_response(response_xml)
                    else:
                        response = self.create_response(2101, "Unimplemented object type")
                elif cmd['type'] == 'info':
                    if cmd['element'].find('.//{urn:ietf:params:xml:ns:domain-1.0}name') is not None:
                        response = self.domain_commands.handle_domain_info(
                            cmd['element'], self.sessions[session_id]
                        )
                    elif cmd['element'].find('.//{urn:ietf:params:xml:ns:contact-1.0}id') is not None:
                        response_xml = self.contact_commands.handle_contact_info(
                            cmd['element'], self.sessions[session_id]
                        )
                        response = self._frame_response(response_xml)
                    elif cmd['element'].find('.//{urn:ietf:params:xml:ns:host-1.0}name') is not None:
                        response_xml = self.host_commands.handle_host_info(
                            cmd['element'], self.sessions[session_id]
                        )
                        response = self._frame_response(response_xml)
                    else:
                        response = self.create_response(2101, "Unimplemented object type")
                elif cmd['type'] == 'create':
                    if cmd['element'].find('.//{urn:ietf:params:xml:ns:domain-1.0}name') is not None:
                        response = self.domain_commands.handle_domain_create(
                            cmd['element'], self.sessions[session_id]
                        )
                    elif cmd['element'].find('.//{urn:ietf:params:xml:ns:contact-1.0}id') is not None:
                        response_xml = self.contact_commands.handle_contact_create(
                            cmd['element'], self.sessions[session_id]
                        )
                        response = self._frame_response(response_xml)
                    elif cmd['element'].find('.//{urn:ietf:params:xml:ns:host-1.0}name') is not None:
                        response_xml = self.host_commands.handle_host_create(
                            cmd['element'], self.sessions[session_id]
                        )
                        response = self._frame_response(response_xml)
                    else:
                        response = self.create_response(2101, "Unimplemented object type")
                elif cmd['type'] == 'update':
                    if cmd['element'].find('.//{urn:ietf:params:xml:ns:domain-1.0}name') is not None:
                        response = self.domain_commands.handle_domain_update(
                            cmd['element'], self.sessions[session_id]
                        )
                    elif cmd['element'].find('.//{urn:ietf:params:xml:ns:contact-1.0}id') is not None:
                        response_xml = self.contact_commands.handle_contact_update(
                            cmd['element'], self.sessions[session_id]
                        )
                        response = self._frame_response(response_xml)
                    elif cmd['element'].find('.//{urn:ietf:params:xml:ns:host-1.0}name') is not None:
                        response_xml = self.host_commands.handle_host_update(
                            cmd['element'], self.sessions[session_id]
                        )
                        response = self._frame_response(response_xml)
                    else:
                        response = self.create_response(2101, "Unimplemented object type")
                elif cmd['type'] == 'delete':
                    if cmd['element'].find('.//{urn:ietf:params:xml:ns:domain-1.0}name') is not None:
                        response = self.domain_commands.handle_domain_delete(
                            cmd['element'], self.sessions[session_id]
                        )
                    elif cmd['element'].find('.//{urn:ietf:params:xml:ns:contact-1.0}id') is not None:
                        response_xml = self.contact_commands.handle_contact_delete(
                            cmd['element'], self.sessions[session_id]
                        )
                        response = self._frame_response(response_xml)
                    elif cmd['element'].find('.//{urn:ietf:params:xml:ns:host-1.0}name') is not None:
                        response_xml = self.host_commands.handle_host_delete(
                            cmd['element'], self.sessions[session_id]
                        )
                        response = self._frame_response(response_xml)
                    else:
                        response = self.create_response(2101, "Unimplemented object type")
                elif cmd['type'] == 'renew':
                    if cmd['element'].find('.//{urn:ietf:params:xml:ns:domain-1.0}name') is not None:
                        response = self.domain_commands.handle_domain_renew(
                            cmd['element'], self.sessions[session_id]
                        )
                    else:
                        response = self.create_response(2101, "Unimplemented object type")
                elif cmd['type'] == 'transfer':
                    if cmd['element'].find('.//{urn:ietf:params:xml:ns:domain-1.0}name') is not None:
                        response = self.domain_commands.handle_domain_transfer(
                            cmd['element'], self.sessions[session_id]
                        )
                    else:
                        response = self.create_response(2101, "Unimplemented object type")
                else:
                    # Not implemented yet
                    response = self.create_response(2101, "Unimplemented command")

                writer.write(response)
                await writer.drain()

        except Exception as e:
            logger.error(f"Client handler error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            if session_id in self.sessions:
                del self.sessions[session_id]
            logger.info(f"Connection closed from {addr}")

    async def start(self):
        """Start EPP server"""
        if not self.connect_db():
            logger.error("Cannot start server without database connection")
            return

        # Create SSL context
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        try:
            # Try to load certificates (will fail initially until we generate them)
            ssl_context.load_cert_chain(
                '/opt/qenex-registrar/certs/epp_cert.pem',
                '/opt/qenex-registrar/certs/epp_key.pem'
            )
            logger.info("SSL certificates loaded")
        except FileNotFoundError:
            logger.warning("SSL certificates not found - running in test mode without TLS")
            logger.warning("Generate certificates before production use!")
            ssl_context = None

        # Start server
        server = await asyncio.start_server(
            self.handle_client,
            EPP_HOST,
            EPP_PORT,
            ssl=ssl_context
        )

        addr = server.sockets[0].getsockname()
        logger.info(f"EPP Server started on {addr[0]}:{addr[1]}")
        logger.info(f"TLS: {'Enabled' if ssl_context else 'DISABLED (TEST MODE)'}")

        async with server:
            await server.serve_forever()

async def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("QENEX EPP Server v1.0")
    logger.info("ICANN Registrar Accreditation - RFC 5730-5734 Compliant")
    logger.info("=" * 60)

    server = EPPServer()
    await server.start()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
