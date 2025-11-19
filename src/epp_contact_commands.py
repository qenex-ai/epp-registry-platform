#!/usr/bin/env python3
"""
EPP Contact Commands Implementation (RFC 5733)
Handles all contact-related EPP operations

Contact commands:
- contact:check - Check contact ID availability
- contact:info - Query contact information
- contact:create - Create new contact
- contact:update - Update contact information
- contact:delete - Delete contact
"""

import xml.etree.ElementTree as ET
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

class EPPContactCommands:
    def __init__(self, db_config):
        self.db_config = db_config
        self.ns = {
            'epp': 'urn:ietf:params:xml:ns:epp-1.0',
            'contact': 'urn:ietf:params:xml:ns:contact-1.0'
        }

    def get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)

    def handle_contact_check(self, element, session):
        """
        Handle contact:check command
        Check if contact IDs are available

        Request:
        <contact:check>
          <contact:id>REG-12345</contact:id>
          <contact:id>ADM-67890</contact:id>
        </contact:check>
        """
        try:
            # Extract contact IDs to check
            contact_ids = []
            for id_elem in element.findall('.//{urn:ietf:params:xml:ns:contact-1.0}id'):
                contact_ids.append(id_elem.text)

            if not contact_ids:
                return self._error_response(2003, "Required parameter missing")

            # Check each contact ID in database
            conn = self.get_db_connection()
            cursor = conn.cursor()

            results = []
            for contact_id in contact_ids:
                cursor.execute(
                    "SELECT contact_handle FROM contacts WHERE contact_handle = %s",
                    (contact_id,)
                )
                exists = cursor.fetchone() is not None
                results.append({
                    'id': contact_id,
                    'avail': '0' if exists else '1',  # 0 = taken, 1 = available
                    'reason': 'In use' if exists else None
                })

            cursor.close()
            conn.close()

            # Build response
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <response>
    <result code="1000">
      <msg>Command completed successfully</msg>
    </result>
    <resData>
      <contact:chkData xmlns:contact="urn:ietf:params:xml:ns:contact-1.0">
"""
            for result in results:
                response += f"""        <contact:cd>
          <contact:id avail="{result['avail']}">{result['id']}</contact:id>
"""
                if result['reason']:
                    response += f"          <contact:reason>{result['reason']}</contact:reason>\n"
                response += "        </contact:cd>\n"

            response += """      </contact:chkData>
    </resData>
    <trID>
      <clTRID>{session_id}</clTRID>
      <svTRID>SRV-{timestamp}</svTRID>
    </trID>
  </response>
</epp>""".format(session_id=session.get('session_id', 'unknown'),
                 timestamp=datetime.utcnow().strftime('%Y%m%d%H%M%S'))

            return response

        except Exception as e:
            return self._error_response(2400, f"Command failed: {str(e)}")

    def handle_contact_info(self, element, session):
        """
        Handle contact:info command
        Query contact information

        Request:
        <contact:info>
          <contact:id>REG-12345</contact:id>
        </contact:info>
        """
        try:
            # Extract contact ID
            id_elem = element.find('.//{urn:ietf:params:xml:ns:contact-1.0}id')
            if id_elem is None:
                return self._error_response(2003, "Required parameter missing")

            contact_id = id_elem.text

            # Query database
            conn = self.get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT contact_handle as id, name, organization as org,
                       street1, street2, street3, city,
                       state_province as sp, postal_code as pc, country_code as cc,
                       phone as voice, fax, email, created_date,
                       last_update as updated_date, status
                FROM contacts
                WHERE contact_handle = %s
            """, (contact_id,))

            contact = cursor.fetchone()
            cursor.close()
            conn.close()

            if not contact:
                return self._error_response(2303, "Object does not exist")

            # Build response
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <response>
    <result code="1000">
      <msg>Command completed successfully</msg>
    </result>
    <resData>
      <contact:infData xmlns:contact="urn:ietf:params:xml:ns:contact-1.0">
        <contact:id>{contact['id']}</contact:id>
        <contact:roid>{contact['id']}-REP</contact:roid>
        <contact:status s="{contact.get('status', 'ok')}"/>
        <contact:postalInfo type="loc">
          <contact:name>{contact['name']}</contact:name>
"""
            if contact['org']:
                response += f"          <contact:org>{contact['org']}</contact:org>\n"

            response += f"""          <contact:addr>
            <contact:street>{contact['street1']}</contact:street>
"""
            if contact['street2']:
                response += f"            <contact:street>{contact['street2']}</contact:street>\n"
            if contact['street3']:
                response += f"            <contact:street>{contact['street3']}</contact:street>\n"

            response += f"""            <contact:city>{contact['city']}</contact:city>
"""
            if contact['sp']:
                response += f"            <contact:sp>{contact['sp']}</contact:sp>\n"

            response += f"""            <contact:pc>{contact['pc']}</contact:pc>
            <contact:cc>{contact['cc']}</contact:cc>
          </contact:addr>
        </contact:postalInfo>
        <contact:voice>{contact['voice']}</contact:voice>
"""
            if contact['fax']:
                response += f"        <contact:fax>{contact['fax']}</contact:fax>\n"

            response += f"""        <contact:email>{contact['email']}</contact:email>
        <contact:clID>QENEX</contact:clID>
        <contact:crID>QENEX</contact:crID>
        <contact:crDate>{contact['created_date'].isoformat() if contact['created_date'] else datetime.utcnow().isoformat()}Z</contact:crDate>
"""
            if contact['updated_date']:
                response += f"        <contact:upDate>{contact['updated_date'].isoformat()}Z</contact:upDate>\n"

            response += """      </contact:infData>
    </resData>
    <trID>
      <clTRID>{session_id}</clTRID>
      <svTRID>SRV-{timestamp}</svTRID>
    </trID>
  </response>
</epp>""".format(session_id=session.get('session_id', 'unknown'),
                 timestamp=datetime.utcnow().strftime('%Y%m%d%H%M%S'))

            return response

        except Exception as e:
            return self._error_response(2400, f"Command failed: {str(e)}")

    def handle_contact_create(self, element, session):
        """
        Handle contact:create command
        Create new contact

        Request:
        <contact:create>
          <contact:id>REG-12345</contact:id>
          <contact:postalInfo type="loc">
            <contact:name>John Doe</contact:name>
            <contact:org>Example Inc</contact:org>
            <contact:addr>
              <contact:street>123 Main St</contact:street>
              <contact:city>London</contact:city>
              <contact:pc>SW1A 1AA</contact:pc>
              <contact:cc>GB</contact:cc>
            </contact:addr>
          </contact:postalInfo>
          <contact:voice>+44.2012345678</contact:voice>
          <contact:email>john@example.com</contact:email>
        </contact:create>
        """
        try:
            # Extract contact data
            contact_ns = '{urn:ietf:params:xml:ns:contact-1.0}'

            id_elem = element.find(f'.//{contact_ns}id')
            if id_elem is None:
                return self._error_response(2003, "Required parameter missing: id")
            contact_id = id_elem.text

            # Extract postal info
            postal_info = element.find(f'.//{contact_ns}postalInfo')
            if postal_info is None:
                return self._error_response(2003, "Required parameter missing: postalInfo")

            name = postal_info.find(f'{contact_ns}name')
            org = postal_info.find(f'{contact_ns}org')
            addr = postal_info.find(f'{contact_ns}addr')

            if name is None or addr is None:
                return self._error_response(2003, "Required parameter missing")

            # Extract address
            streets = addr.findall(f'{contact_ns}street')
            city = addr.find(f'{contact_ns}city')
            sp = addr.find(f'{contact_ns}sp')  # State/Province
            pc = addr.find(f'{contact_ns}pc')  # Postal Code
            cc = addr.find(f'{contact_ns}cc')  # Country Code

            if city is None or pc is None or cc is None:
                return self._error_response(2003, "Required address fields missing")

            # Extract contact methods
            voice = element.find(f'.//{contact_ns}voice')
            fax = element.find(f'.//{contact_ns}fax')
            email = element.find(f'.//{contact_ns}email')

            if voice is None or email is None:
                return self._error_response(2003, "Required parameter missing: voice or email")

            # Insert into database
            conn = self.get_db_connection()
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT INTO contacts (
                        contact_handle, registrar_id, name, organization,
                        street1, street2, street3, city,
                        state_province, postal_code, country_code,
                        phone, fax, email, created_date, status
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, ARRAY['ok']
                    )
                """, (
                    contact_id,
                    session.get('client_id', 'SYSTEM'),
                    name.text,
                    org.text if org is not None else None,
                    streets[0].text if len(streets) > 0 else None,
                    streets[1].text if len(streets) > 1 else None,
                    streets[2].text if len(streets) > 2 else None,
                    city.text,
                    sp.text if sp is not None else None,
                    pc.text,
                    cc.text,
                    voice.text,
                    fax.text if fax is not None else None,
                    email.text,
                    datetime.utcnow()
                ))

                conn.commit()

            except psycopg2.IntegrityError:
                conn.rollback()
                cursor.close()
                conn.close()
                return self._error_response(2302, "Object already exists")

            cursor.close()
            conn.close()

            # Success response
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <response>
    <result code="1000">
      <msg>Command completed successfully</msg>
    </result>
    <resData>
      <contact:creData xmlns:contact="urn:ietf:params:xml:ns:contact-1.0">
        <contact:id>{contact_id}</contact:id>
        <contact:crDate>{datetime.utcnow().isoformat()}Z</contact:crDate>
      </contact:creData>
    </resData>
    <trID>
      <clTRID>{session.get('session_id', 'unknown')}</clTRID>
      <svTRID>SRV-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}</svTRID>
    </trID>
  </response>
</epp>"""

            return response

        except Exception as e:
            return self._error_response(2400, f"Command failed: {str(e)}")

    def handle_contact_update(self, element, session):
        """
        Handle contact:update command
        Update contact information

        Request:
        <contact:update>
          <contact:id>REG-12345</contact:id>
          <contact:chg>
            <contact:postalInfo type="loc">
              <contact:name>John Doe Updated</contact:name>
              <contact:addr>
                <contact:street>456 New St</contact:street>
                <contact:city>Manchester</contact:city>
                <contact:pc>M1 1AA</contact:pc>
                <contact:cc>GB</contact:cc>
              </contact:addr>
            </contact:postalInfo>
            <contact:voice>+44.2099887766</contact:voice>
            <contact:email>newemail@example.com</contact:email>
          </contact:chg>
        </contact:update>
        """
        try:
            contact_ns = '{urn:ietf:params:xml:ns:contact-1.0}'

            # Extract contact ID
            id_elem = element.find(f'.//{contact_ns}id')
            if id_elem is None:
                return self._error_response(2003, "Required parameter missing: id")
            contact_id = id_elem.text

            # Check if contact exists
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT contact_handle FROM contacts WHERE contact_handle = %s", (contact_id,))
            if cursor.fetchone() is None:
                cursor.close()
                conn.close()
                return self._error_response(2303, "Object does not exist")

            # Extract changes
            chg = element.find(f'.//{contact_ns}chg')
            if chg is None:
                cursor.close()
                conn.close()
                return self._error_response(2003, "No changes specified")

            # Build UPDATE query dynamically
            updates = []
            params = []

            # Check for postal info changes
            postal_info = chg.find(f'{contact_ns}postalInfo')
            if postal_info is not None:
                name = postal_info.find(f'{contact_ns}name')
                org = postal_info.find(f'{contact_ns}org')
                addr = postal_info.find(f'{contact_ns}addr')

                if name is not None:
                    updates.append("name = %s")
                    params.append(name.text)

                if org is not None:
                    updates.append("organization = %s")
                    params.append(org.text)

                if addr is not None:
                    streets = addr.findall(f'{contact_ns}street')
                    city = addr.find(f'{contact_ns}city')
                    sp = addr.find(f'{contact_ns}sp')
                    pc = addr.find(f'{contact_ns}pc')
                    cc = addr.find(f'{contact_ns}cc')

                    if len(streets) > 0:
                        updates.append("street1 = %s")
                        params.append(streets[0].text)
                    if len(streets) > 1:
                        updates.append("street2 = %s")
                        params.append(streets[1].text)
                    if len(streets) > 2:
                        updates.append("street3 = %s")
                        params.append(streets[2].text)

                    if city is not None:
                        updates.append("city = %s")
                        params.append(city.text)
                    if sp is not None:
                        updates.append("state_province = %s")
                        params.append(sp.text)
                    if pc is not None:
                        updates.append("postal_code = %s")
                        params.append(pc.text)
                    if cc is not None:
                        updates.append("country_code = %s")
                        params.append(cc.text)

            # Check for contact method changes
            voice = chg.find(f'{contact_ns}voice')
            fax = chg.find(f'{contact_ns}fax')
            email = chg.find(f'{contact_ns}email')

            if voice is not None:
                updates.append("phone = %s")
                params.append(voice.text)
            if fax is not None:
                updates.append("fax = %s")
                params.append(fax.text)
            if email is not None:
                updates.append("email = %s")
                params.append(email.text)

            # Add updated timestamp
            updates.append("last_update = %s")
            params.append(datetime.utcnow())

            # Add contact_id for WHERE clause
            params.append(contact_id)

            # Execute update
            if updates:
                query = f"UPDATE contacts SET {', '.join(updates)} WHERE contact_handle = %s"
                cursor.execute(query, params)
                conn.commit()

            cursor.close()
            conn.close()

            # Success response
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <response>
    <result code="1000">
      <msg>Command completed successfully</msg>
    </result>
    <trID>
      <clTRID>{session.get('session_id', 'unknown')}</clTRID>
      <svTRID>SRV-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}</svTRID>
    </trID>
  </response>
</epp>"""

            return response

        except Exception as e:
            return self._error_response(2400, f"Command failed: {str(e)}")

    def handle_contact_delete(self, element, session):
        """
        Handle contact:delete command
        Delete contact (only if not referenced by any domains)

        Request:
        <contact:delete>
          <contact:id>REG-12345</contact:id>
        </contact:delete>
        """
        try:
            contact_ns = '{urn:ietf:params:xml:ns:contact-1.0}'

            # Extract contact ID
            id_elem = element.find(f'.//{contact_ns}id')
            if id_elem is None:
                return self._error_response(2003, "Required parameter missing: id")
            contact_id = id_elem.text

            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Check if contact exists
            cursor.execute("SELECT contact_handle FROM contacts WHERE contact_handle = %s", (contact_id,))
            if cursor.fetchone() is None:
                cursor.close()
                conn.close()
                return self._error_response(2303, "Object does not exist")

            # Check if contact is referenced by any domains
            cursor.execute("""
                SELECT COUNT(*) FROM domains
                WHERE registrant_id = %s
                   OR admin_contact_id = %s
                   OR tech_contact_id = %s
                   OR billing_contact_id = %s
            """, (contact_id, contact_id, contact_id, contact_id))

            count = cursor.fetchone()[0]
            if count > 0:
                cursor.close()
                conn.close()
                return self._error_response(2305, f"Object association prohibits operation ({count} domains reference this contact)")

            # Delete contact
            cursor.execute("DELETE FROM contacts WHERE contact_handle = %s", (contact_id,))
            conn.commit()

            cursor.close()
            conn.close()

            # Success response
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <response>
    <result code="1000">
      <msg>Command completed successfully</msg>
    </result>
    <trID>
      <clTRID>{session.get('session_id', 'unknown')}</clTRID>
      <svTRID>SRV-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}</svTRID>
    </trID>
  </response>
</epp>"""

            return response

        except Exception as e:
            return self._error_response(2400, f"Command failed: {str(e)}")

    def _error_response(self, code, message):
        """Generate error response"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <response>
    <result code="{code}">
      <msg>{message}</msg>
    </result>
    <trID>
      <svTRID>SRV-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}</svTRID>
    </trID>
  </response>
</epp>"""
