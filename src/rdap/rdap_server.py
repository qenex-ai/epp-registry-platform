#!/usr/bin/env python3
"""
QENEX RDAP Server - RFC 7480-7484 Compliant
Registration Data Access Protocol (Modern WHOIS replacement)
ICANN Requirement for Registrar Accreditation
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import psycopg2
from datetime import datetime
from typing import Optional, List, Dict, Any
import uvicorn
import os

app = FastAPI(
    title="QENEX RDAP Server",
    description="ICANN-compliant RDAP service (RFC 7480-7484)",
    version="1.0.0"
)

# Database configuration
DB_CONFIG = {
    'dbname': os.getenv('EPP_DB_NAME', 'qenex_epp'),
    'user': os.getenv('EPP_DB_USER', 'epp_user'),
    'password': os.getenv('EPP_DB_PASSWORD', 'epp_secure_password_2025'),
    'host': os.getenv('EPP_DB_HOST', 'localhost'),
    'port': os.getenv('EPP_DB_PORT', '5432')
}

def get_db():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG)

def format_rdap_domain(domain_data: dict, contacts: list, nameservers: list) -> dict:
    """Format domain data in RDAP JSON format (RFC 7483)"""
    return {
        "objectClassName": "domain",
        "handle": domain_data.get('domain_id'),
        "ldhName": domain_data.get('domain_name'),
        "unicodeName": domain_data.get('domain_name'),
        "status": domain_data.get('status', ['ok']),
        "events": [
            {
                "eventAction": "registration",
                "eventDate": domain_data.get('creation_date').isoformat() if domain_data.get('creation_date') else None
            },
            {
                "eventAction": "last changed",
                "eventDate": domain_data.get('update_date').isoformat() if domain_data.get('update_date') else datetime.utcnow().isoformat()
            },
            {
                "eventAction": "expiration",
                "eventDate": domain_data.get('expiration_date').isoformat() if domain_data.get('expiration_date') else None
            }
        ],
        "entities": contacts,
        "nameservers": nameservers,
        "secureDNS": {
            "delegationSigned": False  # Update based on DNSSEC status
        },
        "rdapConformance": [
            "rdap_level_0",
            "icann_rdap_response_profile_0",
            "icann_rdap_technical_implementation_guide_0"
        ],
        "notices": [
            {
                "title": "Terms of Use",
                "description": [
                    "By querying the RDAP database, you agree to comply with ICANN's terms of service."
                ],
                "links": [
                    {
                        "value": "https://qenex.ai/rdap/tos",
                        "rel": "terms-of-service",
                        "href": "https://qenex.ai/rdap/tos",
                        "type": "text/html"
                    }
                ]
            },
            {
                "title": "Privacy Policy",
                "description": [
                    "Domain registration data is subject to privacy laws and regulations."
                ],
                "links": [
                    {
                        "value": "https://qenex.ai/privacy",
                        "rel": "privacy-policy",
                        "href": "https://qenex.ai/privacy",
                        "type": "text/html"
                    }
                ]
            }
        ]
    }

@app.get("/")
async def root():
    """RDAP root endpoint"""
    return {
        "rdapConformance": [
            "rdap_level_0"
        ],
        "notices": [
            {
                "title": "QENEX RDAP Service",
                "description": ["ICANN-compliant RDAP server for domain registration data"],
                "links": [
                    {
                        "value": "https://qenex.ai/rdap",
                        "rel": "self",
                        "href": "https://qenex.ai/rdap",
                        "type": "application/rdap+json"
                    }
                ]
            }
        ]
    }

@app.get("/help")
async def help():
    """RDAP help endpoint (RFC 7480 Section 5.3)"""
    return {
        "rdapConformance": ["rdap_level_0"],
        "notices": [
            {
                "title": "RDAP Query Help",
                "description": [
                    "Query domain: /domain/{domain_name}",
                    "Query nameserver: /nameserver/{nameserver_name}",
                    "Query entity: /entity/{entity_handle}",
                    "Examples:",
                    "  /domain/example.org",
                    "  /nameserver/ns1.example.org",
                    "  /entity/REGISTRANT-123"
                ]
            }
        ]
    }

@app.get("/domain/{domain_name}")
async def get_domain(domain_name: str):
    """RDAP domain lookup (RFC 7483 Section 5.3)"""
    try:
        conn = get_db()
        cur = conn.cursor()

        # Query domain
        cur.execute("""
            SELECT domain_id, domain_name, registrar_id, status,
                   creation_date, update_date, expiration_date
            FROM domains
            WHERE LOWER(domain_name) = LOWER(%s)
        """, (domain_name,))

        domain = cur.fetchone()

        if not domain:
            raise HTTPException(
                status_code=404,
                detail={
                    "errorCode": 404,
                    "title": "Not Found",
                    "description": ["The requested domain was not found in the registry."]
                }
            )

        domain_id, name, registrar_id, status, created, updated, expires = domain

        # Query nameservers
        cur.execute("""
            SELECT n.hostname, n.ipv4_address, n.ipv6_address
            FROM nameservers n
            JOIN domain_nameservers dn ON n.nameserver_id = dn.nameserver_id
            WHERE dn.domain_id = %s
        """, (domain_id,))

        nameservers = [
            {
                "objectClassName": "nameserver",
                "ldhName": ns[0],
                "ipAddresses": {
                    "v4": [ns[1]] if ns[1] else [],
                    "v6": [ns[2]] if ns[2] else []
                }
            }
            for ns in cur.fetchall()
        ]

        # Query contacts (registrant, admin, tech)
        cur.execute("""
            SELECT contact_id, name, organization, email, phone
            FROM contacts
            WHERE domain_id = %s
        """, (domain_id,))

        contacts = [
            {
                "objectClassName": "entity",
                "handle": contact[0],
                "roles": ["registrant"],  # Could be admin, tech, billing
                "vcardArray": [
                    "vcard",
                    [
                        ["version", {}, "text", "4.0"],
                        ["fn", {}, "text", contact[1]],
                        ["org", {}, "text", contact[2]] if contact[2] else ["org", {}, "text", ""],
                        ["email", {}, "text", contact[3]],
                        ["tel", {}, "text", contact[4]] if contact[4] else ["tel", {}, "text", ""]
                    ]
                ]
            }
            for contact in cur.fetchall()
        ]

        # Format RDAP response
        response = format_rdap_domain(
            {
                'domain_id': domain_id,
                'domain_name': name,
                'registrar_id': registrar_id,
                'status': status if isinstance(status, list) else [status],
                'creation_date': created,
                'update_date': updated,
                'expiration_date': expires
            },
            contacts,
            nameservers
        )

        cur.close()
        conn.close()

        return JSONResponse(
            content=response,
            media_type="application/rdap+json"
        )

    except psycopg2.Error as e:
        raise HTTPException(
            status_code=500,
            detail={
                "errorCode": 500,
                "title": "Internal Server Error",
                "description": ["Database error occurred"]
            }
        )

@app.get("/nameserver/{nameserver_name}")
async def get_nameserver(nameserver_name: str):
    """RDAP nameserver lookup (RFC 7483 Section 5.2)"""
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT nameserver_id, hostname, ipv4_address, ipv6_address
            FROM nameservers
            WHERE LOWER(hostname) = LOWER(%s)
        """, (nameserver_name,))

        ns = cur.fetchone()

        if not ns:
            raise HTTPException(status_code=404, detail="Nameserver not found")

        response = {
            "objectClassName": "nameserver",
            "handle": ns[0],
            "ldhName": ns[1],
            "ipAddresses": {
                "v4": [ns[2]] if ns[2] else [],
                "v6": [ns[3]] if ns[3] else []
            },
            "rdapConformance": ["rdap_level_0"]
        }

        cur.close()
        conn.close()

        return JSONResponse(content=response, media_type="application/rdap+json")

    except psycopg2.Error:
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/entity/{entity_handle}")
async def get_entity(entity_handle: str):
    """RDAP entity lookup (RFC 7483 Section 5.1)"""
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT contact_id, name, organization, email, phone, address
            FROM contacts
            WHERE contact_id = %s
        """, (entity_handle,))

        entity = cur.fetchone()

        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        response = {
            "objectClassName": "entity",
            "handle": entity[0],
            "vcardArray": [
                "vcard",
                [
                    ["version", {}, "text", "4.0"],
                    ["fn", {}, "text", entity[1]],
                    ["org", {}, "text", entity[2] if entity[2] else ""],
                    ["email", {}, "text", entity[3]],
                    ["tel", {}, "text", entity[4] if entity[4] else ""],
                    ["adr", {}, "text", entity[5] if entity[5] else ""]
                ]
            ],
            "rdapConformance": ["rdap_level_0"]
        }

        cur.close()
        conn.close()

        return JSONResponse(content=response, media_type="application/rdap+json")

    except psycopg2.Error:
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/domains")
async def search_domains(name: Optional[str] = None):
    """RDAP domain search (RFC 7482 Section 3.2)"""
    if not name:
        raise HTTPException(status_code=400, detail="Search parameter 'name' required")

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT domain_name FROM domains
            WHERE domain_name ILIKE %s
            LIMIT 100
        """, (f"%{name}%",))

        domains = [{"ldhName": row[0]} for row in cur.fetchall()]

        cur.close()
        conn.close()

        return JSONResponse(
            content={
                "rdapConformance": ["rdap_level_0"],
                "domainSearchResults": domains
            },
            media_type="application/rdap+json"
        )

    except psycopg2.Error:
        raise HTTPException(status_code=500, detail="Database error")

if __name__ == "__main__":
    uvicorn.run(
        "rdap_server:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info"
    )
