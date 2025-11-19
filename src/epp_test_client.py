#!/usr/bin/env python3
"""
QENEX EPP Test Client
Tests EPP server connectivity and commands
"""

import socket
import ssl
import xml.etree.ElementTree as ET
from datetime import datetime
import sys

class EPPClient:
    """EPP Protocol Test Client"""

    def __init__(self, host, port=700, use_tls=True):
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.sock = None
        self.session_id = None

    def connect(self):
        """Connect to EPP server"""
        print(f"Connecting to {self.host}:{self.port}...")

        # Create socket
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if self.use_tls:
            # Wrap with TLS (disable cert verification for self-signed certs)
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            self.sock = context.wrap_socket(raw_sock, server_hostname=self.host)
        else:
            self.sock = raw_sock

        self.sock.connect((self.host, self.port))
        print(f"✅ Connected to EPP server")

        # Read greeting
        greeting = self.receive()
        print(f"\n📩 Received greeting:")
        print(greeting.decode('utf-8'))
        return greeting

    def send(self, data):
        """Send EPP command with frame header"""
        if isinstance(data, str):
            data = data.encode('utf-8')

        # Add EPP frame header (4 bytes length + 4)
        frame_length = len(data) + 4
        frame = frame_length.to_bytes(4, byteorder='big') + data

        self.sock.sendall(frame)
        print(f"✉️  Sent {len(data)} bytes")

    def receive(self):
        """Receive EPP response"""
        # Read frame length (4 bytes)
        length_data = self.sock.recv(4)
        if not length_data:
            return None

        frame_length = int.from_bytes(length_data, byteorder='big')

        # Read response data (frame_length - 4 bytes already read)
        response_data = b''
        remaining = frame_length - 4

        while remaining > 0:
            chunk = self.sock.recv(min(remaining, 4096))
            if not chunk:
                break
            response_data += chunk
            remaining -= len(chunk)

        return response_data

    def login(self, username, password):
        """Send EPP login command"""
        login_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <login>
      <clID>{username}</clID>
      <pw>{password}</pw>
      <options>
        <version>1.0</version>
        <lang>en</lang>
      </options>
      <svcs>
        <objURI>urn:ietf:params:xml:ns:domain-1.0</objURI>
        <objURI>urn:ietf:params:xml:ns:contact-1.0</objURI>
        <objURI>urn:ietf:params:xml:ns:host-1.0</objURI>
      </svcs>
    </login>
    <clTRID>TEST-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}</clTRID>
  </command>
</epp>"""

        print(f"\n🔐 Logging in as {username}...")
        self.send(login_xml)

        response = self.receive()
        print(f"\n📩 Login response:")
        print(response.decode('utf-8'))

        # Parse response code
        root = ET.fromstring(response.decode('utf-8'))
        result = root.find('.//{urn:ietf:params:xml:ns:epp-1.0}result')
        code = result.get('code')

        if code == '1000':
            print(f"✅ Login successful!")
            return True
        else:
            print(f"❌ Login failed with code {code}")
            return False

    def check_domain(self, domain):
        """Check domain availability"""
        check_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <check>
      <domain:check xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
        <domain:name>{domain}</domain:name>
      </domain:check>
    </check>
    <clTRID>CHECK-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}</clTRID>
  </command>
</epp>"""

        print(f"\n🔍 Checking domain: {domain}")
        self.send(check_xml)

        response = self.receive()
        print(f"\n📩 Check response:")
        print(response.decode('utf-8'))
        return response

    def hello(self):
        """Send hello command to get greeting"""
        hello_xml = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <hello/>
</epp>"""

        print(f"\n👋 Sending hello...")
        self.send(hello_xml)

        response = self.receive()
        print(f"\n📩 Hello response:")
        print(response.decode('utf-8'))
        return response

    def logout(self):
        """Send EPP logout command"""
        logout_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <logout/>
    <clTRID>LOGOUT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}</clTRID>
  </command>
</epp>"""

        print(f"\n👋 Logging out...")
        self.send(logout_xml)

        response = self.receive()
        print(f"\n📩 Logout response:")
        print(response.decode('utf-8'))

    def close(self):
        """Close connection"""
        if self.sock:
            self.sock.close()
            print(f"\n🔌 Connection closed")

def test_local_server():
    """Test local EPP server"""
    print("="*60)
    print("QENEX EPP Server Test - Local (Azure)")
    print("="*60)

    client = EPPClient('localhost', 700, use_tls=True)

    try:
        # Connect and get greeting
        client.connect()

        # Test hello command
        client.hello()

        # Test login
        client.login('test-registrar', 'testpass123')

        # Test domain check
        client.check_domain('example.com')
        client.check_domain('qenex.ai')

        # Logout
        client.logout()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()

def test_gcp_server():
    """Test GCP EPP server"""
    print("\n" + "="*60)
    print("QENEX EPP Server Test - GCP (US)")
    print("="*60)

    client = EPPClient('34.46.93.132', 700, use_tls=True)

    try:
        # Connect and get greeting
        client.connect()

        # Test hello command
        client.hello()

        # Test login
        client.login('test-registrar', 'testpass123')

        # Test domain check
        client.check_domain('test.com')

        # Logout
        client.logout()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'gcp':
        test_gcp_server()
    else:
        test_local_server()

        # Also test GCP
        print("\n\n")
        test_gcp_server()
