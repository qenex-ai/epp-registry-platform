#!/usr/bin/env python3
"""
EPP Host Commands Handler
Implements RFC 5732 - Extensible Provisioning Protocol (EPP) Host Mapping

Commands implemented:
1. host:check - Check host name availability
2. host:info - Query host information
3. host:create - Create new host
4. host:update - Update host information
5. host:delete - Delete host

Author: QENEX LTD
Date: 2025-11-07
"""

import psycopg2
from lxml import etree
from datetime import datetime
import re


class EPPHostCommands:
    """Handler for EPP host (nameserver) commands per RFC 5732"""

    def __init__(self, db_config):
        """
        Initialize EPP host commands handler

        Args:
            db_config: Dictionary with PostgreSQL connection parameters
        """
        self.db_config = db_config
        self.ns = {
            'epp': 'urn:ietf:params:xml:ns:epp-1.0',
            'host': 'urn:ietf:params:xml:ns:host-1.0'
        }

    def get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)

    def _error_response(self, code, message):
        """
        Generate standard EPP error response

        Args:
            code: EPP result code
            message: Human-readable error message

        Returns:
            XML string with error response
        """
        response = f'''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <response>
    <result code="{code}">
      <msg>{message}</msg>
    </result>
    <trID>
      <svTRID>qenex-{datetime.now().strftime('%Y%m%d%H%M%S')}</svTRID>
    </trID>
  </response>
</epp>'''
        return response

    def _validate_hostname(self, hostname):
        """
        Validate hostname format per RFC 952/1123

        Args:
            hostname: Hostname to validate

        Returns:
            True if valid, False otherwise
        """
        if not hostname or len(hostname) > 255:
            return False

        # Each label must be 1-63 characters
        # Labels can contain a-z, 0-9, and hyphens (not at start/end)
        label_pattern = r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$'
        labels = hostname.lower().split('.')

        if len(labels) < 2:  # Must have at least two labels
            return False

        for label in labels:
            if not re.match(label_pattern, label):
                return False

        return True

    def _validate_ip(self, ip, version='v4'):
        """
        Validate IP address format

        Args:
            ip: IP address string
            version: 'v4' or 'v6'

        Returns:
            True if valid, False otherwise
        """
        if version == 'v4':
            # Simple IPv4 validation
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            try:
                return all(0 <= int(part) <= 255 for part in parts)
            except (ValueError, TypeError):
                return False
        elif version == 'v6':
            # Basic IPv6 validation (simplified)
            return ':' in ip and all(c in '0123456789abcdefABCDEF:' for c in ip)

        return False

    # ========================================================================
    # HOST:CHECK - Check host name availability
    # ========================================================================

    def handle_host_check(self, element, session):
        """
        Handle host:check command - check if host names are available

        Args:
            element: lxml Element containing the check command
            session: Dict containing session information (client_id, etc.)

        Returns:
            XML string with check results
        """
        try:
            # Extract host names to check
            host_names = element.xpath('//host:name/text()', namespaces=self.ns)

            if not host_names:
                return self._error_response(2003, 'Required parameter missing')

            conn = self.get_db_connection()
            cur = conn.cursor()

            # Build check results
            check_results = []
            for name in host_names:
                # Validate hostname format
                if not self._validate_hostname(name):
                    check_results.append({
                        'name': name,
                        'avail': '0',
                        'reason': 'Invalid hostname format'
                    })
                    continue

                # Check if host exists in database
                cur.execute(
                    "SELECT id FROM hosts WHERE name = %s",
                    (name.lower(),)
                )
                exists = cur.fetchone() is not None

                check_results.append({
                    'name': name,
                    'avail': '0' if exists else '1',
                    'reason': 'In use' if exists else None
                })

            cur.close()
            conn.close()

            # Build response XML
            cd_elements = []
            for result in check_results:
                reason_attr = f' <host:reason>{result["reason"]}</host:reason>' if result['reason'] else ''
                cd_elements.append(f'''
      <host:cd>
        <host:name avail="{result['avail']}">{result['name']}</host:name>{reason_attr}
      </host:cd>''')

            response = f'''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <response>
    <result code="1000">
      <msg>Command completed successfully</msg>
    </result>
    <resData>
      <host:chkData xmlns:host="urn:ietf:params:xml:ns:host-1.0">{''.join(cd_elements)}
      </host:chkData>
    </resData>
    <trID>
      <svTRID>qenex-{datetime.now().strftime('%Y%m%d%H%M%S')}</svTRID>
    </trID>
  </response>
</epp>'''
            return response

        except Exception as e:
            return self._error_response(2400, f'Command failed: {str(e)}')

    # ========================================================================
    # HOST:INFO - Query host information
    # ========================================================================

    def handle_host_info(self, element, session):
        """
        Handle host:info command - query host information

        Args:
            element: lxml Element containing the info command
            session: Dict containing session information

        Returns:
            XML string with host details
        """
        try:
            # Extract host name
            name = element.xpath('//host:name/text()', namespaces=self.ns)

            if not name:
                return self._error_response(2003, 'Required parameter missing')

            name = name[0].lower()

            conn = self.get_db_connection()
            cur = conn.cursor()

            # Query host information
            cur.execute("""
                SELECT id, name, created_date, updated_date,
                       created_by, updated_by, status
                FROM hosts
                WHERE name = %s
            """, (name,))

            host = cur.fetchone()

            if not host:
                cur.close()
                conn.close()
                return self._error_response(2303, 'Object does not exist')

            host_id, host_name, created_date, updated_date, created_by, updated_by, status = host

            # Query IP addresses
            cur.execute("""
                SELECT ip_address, ip_version
                FROM host_ips
                WHERE host_id = %s
                ORDER BY ip_version, ip_address
            """, (host_id,))

            ips = cur.fetchall()

            cur.close()
            conn.close()

            # Build IP address elements
            addr_elements = []
            for ip, version in ips:
                addr_elements.append(f'''
        <host:addr ip="{version}">{ip}</host:addr>''')

            # Build status elements
            status_elements = f'''
        <host:status s="{status}"/>'''

            # Build updated date if exists
            upDate_element = ''
            if updated_date:
                upDate_element = f'''
        <host:upDate>{updated_date.strftime('%Y-%m-%dT%H:%M:%S.0Z')}</host:upDate>'''

            response = f'''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <response>
    <result code="1000">
      <msg>Command completed successfully</msg>
    </result>
    <resData>
      <host:infData xmlns:host="urn:ietf:params:xml:ns:host-1.0">
        <host:name>{host_name}</host:name>
        <host:roid>{host_id}-QENEX</host:roid>{''.join(status_elements)}{''.join(addr_elements)}
        <host:clID>{created_by}</host:clID>
        <host:crID>{created_by}</host:crID>
        <host:crDate>{created_date.strftime('%Y-%m-%dT%H:%M:%S.0Z')}</host:crDate>{upDate_element}
      </host:infData>
    </resData>
    <trID>
      <svTRID>qenex-{datetime.now().strftime('%Y%m%d%H%M%S')}</svTRID>
    </trID>
  </response>
</epp>'''
            return response

        except Exception as e:
            return self._error_response(2400, f'Command failed: {str(e)}')

    # ========================================================================
    # HOST:CREATE - Create new host
    # ========================================================================

    def handle_host_create(self, element, session):
        """
        Handle host:create command - create new host object

        Args:
            element: lxml Element containing the create command
            session: Dict containing session information

        Returns:
            XML string with creation result
        """
        try:
            # Extract host name
            name = element.xpath('//host:name/text()', namespaces=self.ns)

            if not name:
                return self._error_response(2003, 'Required parameter missing')

            name = name[0].lower()

            # Validate hostname format
            if not self._validate_hostname(name):
                return self._error_response(2005, 'Invalid hostname format')

            # Extract IP addresses (optional)
            addrs = element.xpath('//host:addr', namespaces=self.ns)
            ip_addresses = []

            for addr in addrs:
                ip = addr.text
                version = addr.get('ip', 'v4')

                # Validate IP address
                if not self._validate_ip(ip, version):
                    return self._error_response(2005, f'Invalid IP address: {ip}')

                ip_addresses.append((ip, version))

            conn = self.get_db_connection()
            cur = conn.cursor()

            # Check if host already exists
            cur.execute("SELECT id FROM hosts WHERE name = %s", (name,))
            if cur.fetchone():
                cur.close()
                conn.close()
                return self._error_response(2302, 'Object already exists')

            # Insert host
            client_id = session.get('client_id', 'SYSTEM')
            created_date = datetime.now()

            cur.execute("""
                INSERT INTO hosts (name, created_date, created_by, status)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (name, created_date, client_id, 'ok'))

            host_id = cur.fetchone()[0]

            # Insert IP addresses
            for ip, version in ip_addresses:
                cur.execute("""
                    INSERT INTO host_ips (host_id, ip_address, ip_version)
                    VALUES (%s, %s, %s)
                """, (host_id, ip, version))

            conn.commit()
            cur.close()
            conn.close()

            response = f'''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <response>
    <result code="1000">
      <msg>Command completed successfully</msg>
    </result>
    <resData>
      <host:creData xmlns:host="urn:ietf:params:xml:ns:host-1.0">
        <host:name>{name}</host:name>
        <host:crDate>{created_date.strftime('%Y-%m-%dT%H:%M:%S.0Z')}</host:crDate>
      </host:creData>
    </resData>
    <trID>
      <svTRID>qenex-{datetime.now().strftime('%Y%m%d%H%M%S')}</svTRID>
    </trID>
  </response>
</epp>'''
            return response

        except Exception as e:
            if conn:
                conn.rollback()
            return self._error_response(2400, f'Command failed: {str(e)}')

    # ========================================================================
    # HOST:UPDATE - Update host information
    # ========================================================================

    def handle_host_update(self, element, session):
        """
        Handle host:update command - update host information

        Args:
            element: lxml Element containing the update command
            session: Dict containing session information

        Returns:
            XML string with update result
        """
        try:
            # Extract host name
            name = element.xpath('//host:name/text()', namespaces=self.ns)

            if not name:
                return self._error_response(2003, 'Required parameter missing')

            name = name[0].lower()

            conn = self.get_db_connection()
            cur = conn.cursor()

            # Check if host exists
            cur.execute("SELECT id FROM hosts WHERE name = %s", (name,))
            host = cur.fetchone()

            if not host:
                cur.close()
                conn.close()
                return self._error_response(2303, 'Object does not exist')

            host_id = host[0]

            # Extract add elements (IP addresses to add)
            add_addrs = element.xpath('//host:add/host:addr', namespaces=self.ns)
            for addr in add_addrs:
                ip = addr.text
                version = addr.get('ip', 'v4')

                if not self._validate_ip(ip, version):
                    cur.close()
                    conn.close()
                    return self._error_response(2005, f'Invalid IP address: {ip}')

                # Insert IP address (ignore if duplicate)
                cur.execute("""
                    INSERT INTO host_ips (host_id, ip_address, ip_version)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (host_id, ip_address) DO NOTHING
                """, (host_id, ip, version))

            # Extract rem elements (IP addresses to remove)
            rem_addrs = element.xpath('//host:rem/host:addr', namespaces=self.ns)
            for addr in rem_addrs:
                ip = addr.text

                cur.execute("""
                    DELETE FROM host_ips
                    WHERE host_id = %s AND ip_address = %s
                """, (host_id, ip))

            # Extract status changes (add/rem)
            add_statuses = element.xpath('//host:add/host:status/@s', namespaces=self.ns)
            rem_statuses = element.xpath('//host:rem/host:status/@s', namespaces=self.ns)

            # For simplicity, we'll just update to the first add_status if provided
            if add_statuses:
                cur.execute("""
                    UPDATE hosts
                    SET status = %s, updated_date = %s, updated_by = %s
                    WHERE id = %s
                """, (add_statuses[0], datetime.now(), session.get('client_id', 'SYSTEM'), host_id))
            else:
                # Just update the updated_date
                cur.execute("""
                    UPDATE hosts
                    SET updated_date = %s, updated_by = %s
                    WHERE id = %s
                """, (datetime.now(), session.get('client_id', 'SYSTEM'), host_id))

            conn.commit()
            cur.close()
            conn.close()

            response = f'''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <response>
    <result code="1000">
      <msg>Command completed successfully</msg>
    </result>
    <trID>
      <svTRID>qenex-{datetime.now().strftime('%Y%m%d%H%M%S')}</svTRID>
    </trID>
  </response>
</epp>'''
            return response

        except Exception as e:
            if conn:
                conn.rollback()
            return self._error_response(2400, f'Command failed: {str(e)}')

    # ========================================================================
    # HOST:DELETE - Delete host
    # ========================================================================

    def handle_host_delete(self, element, session):
        """
        Handle host:delete command - delete host object

        Args:
            element: lxml Element containing the delete command
            session: Dict containing session information

        Returns:
            XML string with deletion result
        """
        try:
            # Extract host name
            name = element.xpath('//host:name/text()', namespaces=self.ns)

            if not name:
                return self._error_response(2003, 'Required parameter missing')

            name = name[0].lower()

            conn = self.get_db_connection()
            cur = conn.cursor()

            # Check if host exists
            cur.execute("SELECT id FROM hosts WHERE name = %s", (name,))
            host = cur.fetchone()

            if not host:
                cur.close()
                conn.close()
                return self._error_response(2303, 'Object does not exist')

            host_id = host[0]

            # Check if host is referenced by any domains
            cur.execute("""
                SELECT COUNT(*) FROM domain_hosts WHERE host_id = %s
            """, (host_id,))

            ref_count = cur.fetchone()[0]

            if ref_count > 0:
                cur.close()
                conn.close()
                return self._error_response(2305, 'Object association prohibits operation')

            # Delete IP addresses first (foreign key constraint)
            cur.execute("DELETE FROM host_ips WHERE host_id = %s", (host_id,))

            # Delete host
            cur.execute("DELETE FROM hosts WHERE id = %s", (host_id,))

            conn.commit()
            cur.close()
            conn.close()

            response = f'''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <response>
    <result code="1000">
      <msg>Command completed successfully</msg>
    </result>
    <trID>
      <svTRID>qenex-{datetime.now().strftime('%Y%m%d%H%M%S')}</svTRID>
    </trID>
  </response>
</epp>'''
            return response

        except Exception as e:
            if conn:
                conn.rollback()
            return self._error_response(2400, f'Command failed: {str(e)}')


# Usage example
if __name__ == '__main__':
    # Example database configuration
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'qenex_registrar',
        'user': 'qenex',
        'password': 'your_password'
    }

    handler = EPPHostCommands(db_config)
    print("EPP Host Commands Handler initialized successfully")
    print("Implements RFC 5732 - EPP Host Mapping")
    print("\nSupported commands:")
    print("  - host:check")
    print("  - host:info")
    print("  - host:create")
    print("  - host:update")
    print("  - host:delete")
