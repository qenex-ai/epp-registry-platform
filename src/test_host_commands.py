#!/usr/bin/env python3
"""
Test script for EPP Host Commands
Tests all 5 host commands: check, info, create, update, delete
"""

from lxml import etree
from epp_host_commands import EPPHostCommands

# Database configuration
DB_CONFIG = {
    'dbname': 'qenex_epp',
    'user': 'epp_user',
    'password': 'epp_secure_password_2025',
    'host': 'localhost',
    'port': 5432
}

def create_test_session():
    """Create a test session"""
    return {
        'client_id': 'test-registrar',
        'authenticated': True
    }

def print_response(command_name, response):
    """Pretty print EPP response"""
    print(f"\n{'=' * 60}")
    print(f"TEST: {command_name}")
    print(f"{'=' * 60}")
    try:
        # Parse and pretty print XML
        root = etree.fromstring(response.encode('utf-8'))
        print(etree.tostring(root, pretty_print=True, encoding='unicode'))
    except:
        print(response)
    print(f"{'=' * 60}\n")

def test_host_check():
    """Test host:check command"""
    handler = EPPHostCommands(DB_CONFIG)
    session = create_test_session()

    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <check>
      <host:check xmlns:host="urn:ietf:params:xml:ns:host-1.0">
        <host:name>ns1.example.com</host:name>
        <host:name>ns2.example.com</host:name>
        <host:name>ns1.example.net</host:name>
      </host:check>
    </check>
    <clTRID>ABC-12345</clTRID>
  </command>
</epp>'''

    element = etree.fromstring(xml.encode('utf-8'))
    response = handler.handle_host_check(element, session)
    print_response("HOST CHECK", response)

def test_host_create():
    """Test host:create command"""
    handler = EPPHostCommands(DB_CONFIG)
    session = create_test_session()

    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <create>
      <host:create xmlns:host="urn:ietf:params:xml:ns:host-1.0">
        <host:name>ns1.example.com</host:name>
        <host:addr ip="v4">192.0.2.2</host:addr>
        <host:addr ip="v4">192.0.2.29</host:addr>
        <host:addr ip="v6">1080:0:0:0:8:800:200C:417A</host:addr>
      </host:create>
    </create>
    <clTRID>ABC-12345</clTRID>
  </command>
</epp>'''

    element = etree.fromstring(xml.encode('utf-8'))
    response = handler.handle_host_create(element, session)
    print_response("HOST CREATE", response)

def test_host_info():
    """Test host:info command"""
    handler = EPPHostCommands(DB_CONFIG)
    session = create_test_session()

    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <info>
      <host:info xmlns:host="urn:ietf:params:xml:ns:host-1.0">
        <host:name>ns1.example.com</host:name>
      </host:info>
    </info>
    <clTRID>ABC-12345</clTRID>
  </command>
</epp>'''

    element = etree.fromstring(xml.encode('utf-8'))
    response = handler.handle_host_info(element, session)
    print_response("HOST INFO", response)

def test_host_update():
    """Test host:update command"""
    handler = EPPHostCommands(DB_CONFIG)
    session = create_test_session()

    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <update>
      <host:update xmlns:host="urn:ietf:params:xml:ns:host-1.0">
        <host:name>ns1.example.com</host:name>
        <host:add>
          <host:addr ip="v4">192.0.2.22</host:addr>
          <host:status s="clientUpdateProhibited"/>
        </host:add>
        <host:rem>
          <host:addr ip="v4">192.0.2.2</host:addr>
        </host:rem>
      </host:update>
    </update>
    <clTRID>ABC-12345</clTRID>
  </command>
</epp>'''

    element = etree.fromstring(xml.encode('utf-8'))
    response = handler.handle_host_update(element, session)
    print_response("HOST UPDATE", response)

def test_host_delete():
    """Test host:delete command"""
    handler = EPPHostCommands(DB_CONFIG)
    session = create_test_session()

    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <delete>
      <host:delete xmlns:host="urn:ietf:params:xml:ns:host-1.0">
        <host:name>ns1.example.com</host:name>
      </host:delete>
    </delete>
    <clTRID>ABC-12345</clTRID>
  </command>
</epp>'''

    element = etree.fromstring(xml.encode('utf-8'))
    response = handler.handle_host_delete(element, session)
    print_response("HOST DELETE", response)

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("EPP HOST COMMANDS TEST SUITE")
    print("=" * 60)

    try:
        # Test in order: check -> create -> info -> update -> delete
        print("\n1. Testing HOST CHECK (before creation)")
        test_host_check()

        print("\n2. Testing HOST CREATE")
        test_host_create()

        print("\n3. Testing HOST INFO")
        test_host_info()

        print("\n4. Testing HOST UPDATE")
        test_host_update()

        print("\n5. Testing HOST INFO (after update)")
        test_host_info()

        print("\n6. Testing HOST DELETE")
        test_host_delete()

        print("\n7. Testing HOST CHECK (after deletion)")
        test_host_check()

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
