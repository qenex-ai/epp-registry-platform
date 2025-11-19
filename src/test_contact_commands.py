#!/usr/bin/env python3
"""
Test script for EPP Contact Commands
Tests all 5 contact commands: check, info, create, update, delete
"""

from lxml import etree
from epp_contact_commands import EPPContactCommands

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

def test_contact_check():
    """Test contact:check command"""
    handler = EPPContactCommands(DB_CONFIG)
    session = create_test_session()

    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <check>
      <contact:check xmlns:contact="urn:ietf:params:xml:ns:contact-1.0">
        <contact:id>sh8013</contact:id>
        <contact:id>sah8013</contact:id>
        <contact:id>8013sah</contact:id>
      </contact:check>
    </check>
    <clTRID>ABC-12345</clTRID>
  </command>
</epp>'''

    element = etree.fromstring(xml.encode('utf-8'))
    response = handler.handle_contact_check(element, session)
    print_response("CONTACT CHECK", response)

def test_contact_create():
    """Test contact:create command"""
    handler = EPPContactCommands(DB_CONFIG)
    session = create_test_session()

    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <create>
      <contact:create xmlns:contact="urn:ietf:params:xml:ns:contact-1.0">
        <contact:id>sh8013</contact:id>
        <contact:postalInfo type="int">
          <contact:name>John Doe</contact:name>
          <contact:org>Example Inc.</contact:org>
          <contact:addr>
            <contact:street>123 Example Dr.</contact:street>
            <contact:street>Suite 100</contact:street>
            <contact:city>Dulles</contact:city>
            <contact:sp>VA</contact:sp>
            <contact:pc>20166-6503</contact:pc>
            <contact:cc>US</contact:cc>
          </contact:addr>
        </contact:postalInfo>
        <contact:voice>+1.7035555555</contact:voice>
        <contact:fax>+1.7035555556</contact:fax>
        <contact:email>jdoe@example.com</contact:email>
      </contact:create>
    </create>
    <clTRID>ABC-12345</clTRID>
  </command>
</epp>'''

    element = etree.fromstring(xml.encode('utf-8'))
    response = handler.handle_contact_create(element, session)
    print_response("CONTACT CREATE", response)

def test_contact_info():
    """Test contact:info command"""
    handler = EPPContactCommands(DB_CONFIG)
    session = create_test_session()

    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <info>
      <contact:info xmlns:contact="urn:ietf:params:xml:ns:contact-1.0">
        <contact:id>sh8013</contact:id>
      </contact:info>
    </info>
    <clTRID>ABC-12345</clTRID>
  </command>
</epp>'''

    element = etree.fromstring(xml.encode('utf-8'))
    response = handler.handle_contact_info(element, session)
    print_response("CONTACT INFO", response)

def test_contact_update():
    """Test contact:update command"""
    handler = EPPContactCommands(DB_CONFIG)
    session = create_test_session()

    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <update>
      <contact:update xmlns:contact="urn:ietf:params:xml:ns:contact-1.0">
        <contact:id>sh8013</contact:id>
        <contact:chg>
          <contact:postalInfo type="int">
            <contact:name>John Doe Updated</contact:name>
            <contact:org>Example Corporation</contact:org>
            <contact:addr>
              <contact:street>456 New St.</contact:street>
              <contact:city>Dulles</contact:city>
              <contact:sp>VA</contact:sp>
              <contact:pc>20166</contact:pc>
              <contact:cc>US</contact:cc>
            </contact:addr>
          </contact:postalInfo>
          <contact:email>john.doe@example.com</contact:email>
        </contact:chg>
      </contact:update>
    </update>
    <clTRID>ABC-12345</clTRID>
  </command>
</epp>'''

    element = etree.fromstring(xml.encode('utf-8'))
    response = handler.handle_contact_update(element, session)
    print_response("CONTACT UPDATE", response)

def test_contact_delete():
    """Test contact:delete command"""
    handler = EPPContactCommands(DB_CONFIG)
    session = create_test_session()

    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <delete>
      <contact:delete xmlns:contact="urn:ietf:params:xml:ns:contact-1.0">
        <contact:id>sh8013</contact:id>
      </contact:delete>
    </delete>
    <clTRID>ABC-12345</clTRID>
  </command>
</epp>'''

    element = etree.fromstring(xml.encode('utf-8'))
    response = handler.handle_contact_delete(element, session)
    print_response("CONTACT DELETE", response)

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("EPP CONTACT COMMANDS TEST SUITE")
    print("=" * 60)

    try:
        # Test in order: check -> create -> info -> update -> delete
        print("\n1. Testing CONTACT CHECK (before creation)")
        test_contact_check()

        print("\n2. Testing CONTACT CREATE")
        test_contact_create()

        print("\n3. Testing CONTACT INFO")
        test_contact_info()

        print("\n4. Testing CONTACT UPDATE")
        test_contact_update()

        print("\n5. Testing CONTACT INFO (after update)")
        test_contact_info()

        print("\n6. Testing CONTACT DELETE")
        test_contact_delete()

        print("\n7. Testing CONTACT CHECK (after deletion)")
        test_contact_check()

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
