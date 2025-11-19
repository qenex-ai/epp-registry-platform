#!/usr/bin/env python3
"""
QENEX EPP Domain Commands Implementation
RFC 5731 - Domain Name Mapping for EPP
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import secrets
import logging

logger = logging.getLogger('EPP-Domain-Commands')

class EPPDomainCommands:
    """EPP Domain Command Handlers (RFC 5731)"""

    def __init__(self, db_conn):
        self.db_conn = db_conn

    def handle_domain_check(self, element, session):
        """
        Handle domain:check command
        Check if domains are available for registration
        """
        try:
            # Parse domain names from request
            domain_names = []
            for name_elem in element.findall('.//{urn:ietf:params:xml:ns:domain-1.0}name'):
                domain_names.append(name_elem.text.lower())

            if not domain_names:
                return self.create_error_response(2003, "Required parameter missing")

            # Check each domain in database
            cursor = self.db_conn.cursor()
            results = []

            for domain in domain_names:
                cursor.execute(
                    "SELECT domain_name FROM domains WHERE domain_name = %s",
                    (domain,)
                )
                exists = cursor.fetchone() is not None

                results.append({
                    'name': domain,
                    'avail': '0' if exists else '1',  # 0 = taken, 1 = available
                    'reason': 'In use' if exists else None
                })

            cursor.close()

            # Build response XML
            result_xml = '<resData><domain:chkData xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">'
            for r in results:
                result_xml += f'<domain:cd><domain:name avail="{r["avail"]}">{r["name"]}</domain:name>'
                if r['reason']:
                    result_xml += f'<domain:reason>{r["reason"]}</domain:reason>'
                result_xml += '</domain:cd>'
            result_xml += '</domain:chkData></resData>'

            return self.create_success_response(1000, "Command completed successfully", result_xml)

        except Exception as e:
            logger.error(f"domain:check error: {e}", exc_info=True)
            return self.create_error_response(2400, "Command failed")

    def handle_domain_info(self, element, session):
        """
        Handle domain:info command
        Query domain information
        """
        try:
            # Parse domain name
            name_elem = element.find('.//{urn:ietf:params:xml:ns:domain-1.0}name')
            if name_elem is None:
                return self.create_error_response(2003, "Required parameter missing")

            domain_name = name_elem.text.lower()

            # Query database
            cursor = self.db_conn.cursor()
            cursor.execute("""
                SELECT d.domain_name, d.registrar_id, d.creation_date, d.expiration_date,
                       d.last_update, d.status, d.auth_code, d.registrant_id,
                       d.admin_contact_id, d.tech_contact_id
                FROM domains d
                WHERE d.domain_name = %s
            """, (domain_name,))

            domain = cursor.fetchone()

            if not domain:
                cursor.close()
                return self.create_error_response(2303, "Object does not exist")

            # Get nameservers
            cursor.execute("""
                SELECT n.hostname
                FROM domain_nameservers dn
                JOIN nameservers n ON dn.nameserver_id = n.nameserver_id
                WHERE dn.domain_id = (SELECT domain_id FROM domains WHERE domain_name = %s)
            """, (domain_name,))
            nameservers = [row[0] for row in cursor.fetchall()]
            cursor.close()

            # Build response XML
            status_list = domain[5] if isinstance(domain[5], list) else ['ok']

            result_xml = f'''<resData>
<domain:infData xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
  <domain:name>{domain[0]}</domain:name>
  <domain:roid>{domain[0].upper().replace(".", "-")}-QENEX</domain:roid>
  {''.join(f"<domain:status s='{s}'/>" for s in status_list)}
  <domain:registrant>{domain[7] if domain[7] else 'REDACTED'}</domain:registrant>
  <domain:contact type="admin">{domain[8] if domain[8] else 'REDACTED'}</domain:contact>
  <domain:contact type="tech">{domain[9] if domain[9] else 'REDACTED'}</domain:contact>
  {''.join(f"<domain:ns><domain:hostObj>{ns}</domain:hostObj></domain:ns>" for ns in nameservers)}
  <domain:clID>{domain[1]}</domain:clID>
  <domain:crID>{domain[1]}</domain:crID>
  <domain:crDate>{domain[2].isoformat()}Z</domain:crDate>
  <domain:upDate>{domain[4].isoformat()}Z</domain:upDate>
  <domain:exDate>{domain[3].isoformat()}Z</domain:exDate>
  <domain:authInfo><domain:pw>{domain[6] if domain[6] else 'REDACTED'}</domain:pw></domain:authInfo>
</domain:infData>
</resData>'''

            return self.create_success_response(1000, "Command completed successfully", result_xml)

        except Exception as e:
            logger.error(f"domain:info error: {e}", exc_info=True)
            return self.create_error_response(2400, "Command failed")

    def handle_domain_create(self, element, session):
        """
        Handle domain:create command
        Register a new domain
        """
        try:
            # Parse domain creation request
            name_elem = element.find('.//{urn:ietf:params:xml:ns:domain-1.0}name')
            period_elem = element.find('.//{urn:ietf:params:xml:ns:domain-1.0}period')
            registrant_elem = element.find('.//{urn:ietf:params:xml:ns:domain-1.0}registrant')
            auth_elem = element.find('.//{urn:ietf:params:xml:ns:domain-1.0}pw')

            if name_elem is None:
                return self.create_error_response(2003, "Required parameter missing")

            domain_name = name_elem.text.lower()
            period = int(period_elem.text) if period_elem is not None else 1
            registrant = registrant_elem.text if registrant_elem is not None else 'DEFAULT'
            auth_code = auth_elem.text if auth_elem is not None else secrets.token_urlsafe(16)

            # Check if domain already exists
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT domain_id FROM domains WHERE domain_name = %s", (domain_name,))
            if cursor.fetchone():
                cursor.close()
                return self.create_error_response(2302, "Object exists")

            # Get registrar ID from session
            registrar_id = session.get('clID', 'unknown')

            # Calculate expiration date
            creation_date = datetime.utcnow()
            expiration_date = creation_date + timedelta(days=period * 365)

            # Insert domain into database
            cursor.execute("""
                INSERT INTO domains (
                    domain_name, registrar_id, creation_date, expiration_date,
                    auth_code, registrant_id, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING domain_id
            """, (domain_name, registrar_id, creation_date, expiration_date,
                  auth_code, registrant, ['ok']))

            domain_id = cursor.fetchone()[0]
            self.db_conn.commit()

            # Get nameservers if provided
            nameservers = []
            for ns_elem in element.findall('.//{urn:ietf:params:xml:ns:domain-1.0}hostObj'):
                nameservers.append(ns_elem.text.lower())

            # Add nameservers
            for ns_hostname in nameservers:
                # Find or create nameserver
                cursor.execute(
                    "SELECT nameserver_id FROM nameservers WHERE hostname = %s",
                    (ns_hostname,)
                )
                ns_row = cursor.fetchone()

                if ns_row:
                    ns_id = ns_row[0]
                else:
                    cursor.execute(
                        "INSERT INTO nameservers (hostname) VALUES (%s) RETURNING nameserver_id",
                        (ns_hostname,)
                    )
                    ns_id = cursor.fetchone()[0]

                # Link to domain
                cursor.execute(
                    "INSERT INTO domain_nameservers (domain_id, nameserver_id) VALUES (%s, %s)",
                    (domain_id, ns_id)
                )

            self.db_conn.commit()
            cursor.close()

            # Build response
            result_xml = f'''<resData>
<domain:creData xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
  <domain:name>{domain_name}</domain:name>
  <domain:crDate>{creation_date.isoformat()}Z</domain:crDate>
  <domain:exDate>{expiration_date.isoformat()}Z</domain:exDate>
</domain:creData>
</resData>'''

            logger.info(f"Domain created: {domain_name} by {registrar_id}")
            return self.create_success_response(1000, "Command completed successfully", result_xml)

        except Exception as e:
            logger.error(f"domain:create error: {e}", exc_info=True)
            if self.db_conn:
                self.db_conn.rollback()
            return self.create_error_response(2400, "Command failed")

    def handle_domain_update(self, element, session):
        """
        Handle domain:update command
        Modify domain information (nameservers, contacts, status)
        """
        try:
            # Parse domain name
            name_elem = element.find('.//{urn:ietf:params:xml:ns:domain-1.0}name')
            if name_elem is None:
                return self.create_error_response(2003, "Required parameter missing")

            domain_name = name_elem.text.lower()

            # Verify domain exists and belongs to registrar
            cursor = self.db_conn.cursor()
            cursor.execute(
                "SELECT domain_id, registrar_id FROM domains WHERE domain_name = %s",
                (domain_name,)
            )
            domain_row = cursor.fetchone()

            if not domain_row:
                cursor.close()
                return self.create_error_response(2303, "Object does not exist")

            domain_id, registrar_id = domain_row

            # Check authorization
            if registrar_id != session.get('clID'):
                cursor.close()
                return self.create_error_response(2201, "Authorization error")

            # Handle nameserver additions
            add_elem = element.find('.//{urn:ietf:params:xml:ns:domain-1.0}add')
            if add_elem:
                for ns_elem in add_elem.findall('.//{urn:ietf:params:xml:ns:domain-1.0}hostObj'):
                    ns_hostname = ns_elem.text.lower()

                    # Find or create nameserver
                    cursor.execute(
                        "SELECT nameserver_id FROM nameservers WHERE hostname = %s",
                        (ns_hostname,)
                    )
                    ns_row = cursor.fetchone()

                    if ns_row:
                        ns_id = ns_row[0]
                    else:
                        cursor.execute(
                            "INSERT INTO nameservers (hostname) VALUES (%s) RETURNING nameserver_id",
                            (ns_hostname,)
                        )
                        ns_id = cursor.fetchone()[0]

                    # Link to domain (if not already linked)
                    cursor.execute("""
                        INSERT INTO domain_nameservers (domain_id, nameserver_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, (domain_id, ns_id))

            # Handle nameserver removals
            rem_elem = element.find('.//{urn:ietf:params:xml:ns:domain-1.0}rem')
            if rem_elem:
                for ns_elem in rem_elem.findall('.//{urn:ietf:params:xml:ns:domain-1.0}hostObj'):
                    ns_hostname = ns_elem.text.lower()
                    cursor.execute("""
                        DELETE FROM domain_nameservers
                        WHERE domain_id = %s AND nameserver_id = (
                            SELECT nameserver_id FROM nameservers WHERE hostname = %s
                        )
                    """, (domain_id, ns_hostname))

            # Update last_update timestamp
            cursor.execute(
                "UPDATE domains SET last_update = %s WHERE domain_id = %s",
                (datetime.utcnow(), domain_id)
            )

            self.db_conn.commit()
            cursor.close()

            logger.info(f"Domain updated: {domain_name} by {session.get('clID')}")
            return self.create_success_response(1000, "Command completed successfully")

        except Exception as e:
            logger.error(f"domain:update error: {e}", exc_info=True)
            if self.db_conn:
                self.db_conn.rollback()
            return self.create_error_response(2400, "Command failed")

    def handle_domain_delete(self, element, session):
        """
        Handle domain:delete command
        Delete/cancel a domain
        """
        try:
            # Parse domain name
            name_elem = element.find('.//{urn:ietf:params:xml:ns:domain-1.0}name')
            if name_elem is None:
                return self.create_error_response(2003, "Required parameter missing")

            domain_name = name_elem.text.lower()

            # Verify domain exists and authorization
            cursor = self.db_conn.cursor()
            cursor.execute(
                "SELECT domain_id, registrar_id, status FROM domains WHERE domain_name = %s",
                (domain_name,)
            )
            domain_row = cursor.fetchone()

            if not domain_row:
                cursor.close()
                return self.create_error_response(2303, "Object does not exist")

            domain_id, registrar_id, status = domain_row

            # Check authorization
            if registrar_id != session.get('clID'):
                cursor.close()
                return self.create_error_response(2201, "Authorization error")

            # Check if domain is locked
            if 'clientDeleteProhibited' in (status or []):
                cursor.close()
                return self.create_error_response(2304, "Object status prohibits operation")

            # Delete domain (cascade will handle nameserver associations)
            cursor.execute("DELETE FROM domains WHERE domain_id = %s", (domain_id,))
            self.db_conn.commit()
            cursor.close()

            logger.info(f"Domain deleted: {domain_name} by {session.get('clID')}")
            return self.create_success_response(1000, "Command completed successfully")

        except Exception as e:
            logger.error(f"domain:delete error: {e}", exc_info=True)
            if self.db_conn:
                self.db_conn.rollback()
            return self.create_error_response(2400, "Command failed")

    def handle_domain_renew(self, element, session):
        """
        Handle domain:renew command
        Renew domain registration
        """
        try:
            # Parse parameters
            name_elem = element.find('.//{urn:ietf:params:xml:ns:domain-1.0}name')
            cur_exp_date_elem = element.find('.//{urn:ietf:params:xml:ns:domain-1.0}curExpDate')
            period_elem = element.find('.//{urn:ietf:params:xml:ns:domain-1.0}period')

            if name_elem is None or cur_exp_date_elem is None:
                return self.create_error_response(2003, "Required parameter missing")

            domain_name = name_elem.text.lower()
            period = int(period_elem.text) if period_elem is not None else 1

            # Verify domain
            cursor = self.db_conn.cursor()
            cursor.execute(
                "SELECT domain_id, registrar_id, expiration_date FROM domains WHERE domain_name = %s",
                (domain_name,)
            )
            domain_row = cursor.fetchone()

            if not domain_row:
                cursor.close()
                return self.create_error_response(2303, "Object does not exist")

            domain_id, registrar_id, current_exp_date = domain_row

            # Check authorization
            if registrar_id != session.get('clID'):
                cursor.close()
                return self.create_error_response(2201, "Authorization error")

            # Calculate new expiration date
            new_exp_date = current_exp_date + timedelta(days=period * 365)

            # Update domain
            cursor.execute(
                "UPDATE domains SET expiration_date = %s, last_update = %s WHERE domain_id = %s",
                (new_exp_date, datetime.utcnow(), domain_id)
            )
            self.db_conn.commit()
            cursor.close()

            # Build response
            result_xml = f'''<resData>
<domain:renData xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
  <domain:name>{domain_name}</domain:name>
  <domain:exDate>{new_exp_date.isoformat()}Z</domain:exDate>
</domain:renData>
</resData>'''

            logger.info(f"Domain renewed: {domain_name} by {session.get('clID')} for {period} years")
            return self.create_success_response(1000, "Command completed successfully", result_xml)

        except Exception as e:
            logger.error(f"domain:renew error: {e}", exc_info=True)
            if self.db_conn:
                self.db_conn.rollback()
            return self.create_error_response(2400, "Command failed")

    def handle_domain_transfer(self, element, session, operation='query'):
        """
        Handle domain:transfer command
        Transfer domain between registrars
        """
        try:
            # Parse domain name and auth code
            name_elem = element.find('.//{urn:ietf:params:xml:ns:domain-1.0}name')
            auth_elem = element.find('.//{urn:ietf:params:xml:ns:domain-1.0}pw')

            if name_elem is None:
                return self.create_error_response(2003, "Required parameter missing")

            domain_name = name_elem.text.lower()
            auth_code = auth_elem.text if auth_elem is not None else None

            # Get transfer operation type
            transfer_elem = element.find('.//{urn:ietf:params:xml:ns:epp-1.0}transfer')
            op = transfer_elem.get('op', 'query') if transfer_elem is not None else 'query'

            cursor = self.db_conn.cursor()

            if op == 'query':
                # Query transfer status
                cursor.execute("""
                    SELECT transfer_status, request_date
                    FROM transfers
                    WHERE domain_id = (SELECT domain_id FROM domains WHERE domain_name = %s)
                    ORDER BY request_date DESC LIMIT 1
                """, (domain_name,))
                transfer = cursor.fetchone()

                if not transfer:
                    cursor.close()
                    return self.create_error_response(2303, "No transfer found")

                result_xml = f'''<resData>
<domain:trnData xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
  <domain:name>{domain_name}</domain:name>
  <domain:trStatus>{transfer[0]}</domain:trStatus>
  <domain:reID>{session.get('clID')}</domain:reID>
  <domain:reDate>{transfer[1].isoformat()}Z</domain:reDate>
</domain:trnData>
</resData>'''
                cursor.close()
                return self.create_success_response(1000, "Command completed successfully", result_xml)

            elif op == 'request':
                # Request transfer - requires auth code
                if not auth_code:
                    cursor.close()
                    return self.create_error_response(2003, "Auth code required")

                # Verify auth code
                cursor.execute(
                    "SELECT domain_id, registrar_id, auth_code FROM domains WHERE domain_name = %s",
                    (domain_name,)
                )
                domain_row = cursor.fetchone()

                if not domain_row:
                    cursor.close()
                    return self.create_error_response(2303, "Object does not exist")

                domain_id, current_registrar, stored_auth_code = domain_row

                if auth_code != stored_auth_code:
                    cursor.close()
                    return self.create_error_response(2202, "Invalid authorization information")

                # Create transfer request
                cursor.execute("""
                    INSERT INTO transfers (domain_id, old_registrar, new_registrar, transfer_status, auth_code)
                    VALUES (%s, %s, %s, 'pending', %s)
                    RETURNING transfer_id, request_date
                """, (domain_id, current_registrar, session.get('clID'), auth_code))

                transfer_id, request_date = cursor.fetchone()
                self.db_conn.commit()
                cursor.close()

                result_xml = f'''<resData>
<domain:trnData xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
  <domain:name>{domain_name}</domain:name>
  <domain:trStatus>pending</domain:trStatus>
  <domain:reID>{session.get('clID')}</domain:reID>
  <domain:reDate>{request_date.isoformat()}Z</domain:reDate>
</domain:trnData>
</resData>'''

                logger.info(f"Transfer requested: {domain_name} to {session.get('clID')}")
                return self.create_success_response(1001, "Command completed successfully; action pending", result_xml)

            else:
                cursor.close()
                return self.create_error_response(2102, "Unimplemented option")

        except Exception as e:
            logger.error(f"domain:transfer error: {e}", exc_info=True)
            if self.db_conn:
                self.db_conn.rollback()
            return self.create_error_response(2400, "Command failed")

    def create_success_response(self, code, msg, result_data=None):
        """Create EPP success response"""
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

        response_bytes = response.encode('utf-8')
        frame_length = len(response_bytes) + 4
        return frame_length.to_bytes(4, byteorder='big') + response_bytes

    def create_error_response(self, code, msg):
        """Create EPP error response"""
        return self.create_success_response(code, msg, None)
