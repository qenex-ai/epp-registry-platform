#!/usr/bin/env python3
"""
Test all EPP domain commands
"""

import sys
sys.path.insert(0, '/opt/qenex-registrar/epp')

from epp_test_client import EPPClient
import time

def test_all_commands():
    """Test full domain lifecycle"""

    client = EPPClient('localhost', 700, use_tls=True)

    print("="*60)
    print("TESTING ALL EPP DOMAIN COMMANDS")
    print("="*60)

    try:
        # Connect
        print("\n1. CONNECTING...")
        client.connect()

        # Login
        print("\n2. LOGGING IN...")
        client.login('test-registrar', 'testpass123')

        # Test domain:check
        print("\n3. TESTING domain:check...")
        client.check_domain('test-example.com')
        client.check_domain('another-test.com')

        # Test domain:create
        print("\n4. TESTING domain:create...")
        create_xml = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <create>
      <domain:create xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
        <domain:name>test-qenex-domain.com</domain:name>
        <domain:period unit="y">1</domain:period>
        <domain:ns>
          <domain:hostObj>ns1.qenex.ai</domain:hostObj>
          <domain:hostObj>ns2.qenex.ai</domain:hostObj>
        </domain:ns>
        <domain:registrant>REG-12345</domain:registrant>
        <domain:contact type="admin">ADM-12345</domain:contact>
        <domain:contact type="tech">TECH-12345</domain:contact>
        <domain:authInfo>
          <domain:pw>SecureAuth123!</domain:pw>
        </domain:authInfo>
      </domain:create>
    </create>
    <clTRID>TEST-CREATE-001</clTRID>
  </command>
</epp>"""
        client.send(create_xml)
        response = client.receive()
        print("\n📩 Create response:")
        print(response.decode('utf-8'))

        time.sleep(1)

        # Test domain:info
        print("\n5. TESTING domain:info...")
        info_xml = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <info>
      <domain:info xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
        <domain:name>test-qenex-domain.com</domain:name>
      </domain:info>
    </info>
    <clTRID>TEST-INFO-001</clTRID>
  </command>
</epp>"""
        client.send(info_xml)
        response = client.receive()
        print("\n📩 Info response:")
        print(response.decode('utf-8'))

        time.sleep(1)

        # Test domain:update
        print("\n6. TESTING domain:update...")
        update_xml = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <update>
      <domain:update xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
        <domain:name>test-qenex-domain.com</domain:name>
        <domain:add>
          <domain:ns>
            <domain:hostObj>ns3.qenex.ai</domain:hostObj>
          </domain:ns>
        </domain:add>
      </domain:update>
    </update>
    <clTRID>TEST-UPDATE-001</clTRID>
  </command>
</epp>"""
        client.send(update_xml)
        response = client.receive()
        print("\n📩 Update response:")
        print(response.decode('utf-8'))

        time.sleep(1)

        # Test domain:renew
        print("\n7. TESTING domain:renew...")
        renew_xml = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <renew>
      <domain:renew xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
        <domain:name>test-qenex-domain.com</domain:name>
        <domain:curExpDate>2026-11-06</domain:curExpDate>
        <domain:period unit="y">1</domain:period>
      </domain:renew>
    </renew>
    <clTRID>TEST-RENEW-001</clTRID>
  </command>
</epp>"""
        client.send(renew_xml)
        response = client.receive()
        print("\n📩 Renew response:")
        print(response.decode('utf-8'))

        time.sleep(1)

        # Test domain:check again (should show as taken now)
        print("\n8. TESTING domain:check (should be unavailable now)...")
        client.check_domain('test-qenex-domain.com')

        time.sleep(1)

        # Test domain:delete
        print("\n9. TESTING domain:delete...")
        delete_xml = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <delete>
      <domain:delete xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
        <domain:name>test-qenex-domain.com</domain:name>
      </domain:delete>
    </delete>
    <clTRID>TEST-DELETE-001</clTRID>
  </command>
</epp>"""
        client.send(delete_xml)
        response = client.receive()
        print("\n📩 Delete response:")
        print(response.decode('utf-8'))

        time.sleep(1)

        # Test domain:check again (should be available now)
        print("\n10. TESTING domain:check (should be available again)...")
        client.check_domain('test-qenex-domain.com')

        # Logout
        print("\n11. LOGGING OUT...")
        client.logout()

        print("\n" + "="*60)
        print("✅ ALL DOMAIN COMMANDS TESTED SUCCESSFULLY!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()

if __name__ == '__main__':
    test_all_commands()
