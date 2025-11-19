# API Documentation

## EPP Server API

### Connection
```python
import socket
import ssl

# Connect to EPP server
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('epp.example.com', 700))

# Wrap with TLS
ssl_sock = ssl.wrap_socket(sock)

# Read greeting
greeting = ssl_sock.recv(4096)
print(greeting.decode())
```

### Domain Registration
```xml
<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <create>
      <domain:create xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
        <domain:name>example.com</domain:name>
        <domain:period unit="y">2</domain:period>
        <domain:ns>
          <domain:hostObj>ns1.example.com</domain:hostObj>
          <domain:hostObj>ns2.example.com</domain:hostObj>
        </domain:ns>
        <domain:registrant>SH8013</domain:registrant>
        <domain:contact type="admin">SH8013</domain:contact>
        <domain:contact type="tech">SH8013</domain:contact>
        <domain:authInfo>
          <domain:pw>2fooBAR</domain:pw>
        </domain:authInfo>
      </domain:create>
    </create>
    <clTRID>ABC-12345</clTRID>
  </command>
</epp>
```

## RDAP API

### Query Domain
```bash
curl https://rdap.example.com/domain/google.com
```

### Response
```json
{
  "objectClassName": "domain",
  "handle": "123",
  "ldhName": "google.com",
  "status": ["active"],
  "nameservers": [
    {"ldhName": "ns1.google.com"},
    {"ldhName": "ns2.google.com"}
  ],
  "events": [
    {
      "eventAction": "registration",
      "eventDate": "2000-01-01T00:00:00Z"
    }
  ]
}
```

## WHOIS Service

### Query
```bash
whois -h whois.example.com google.com
```

### Response
```
Domain Name: GOOGLE.COM
Registry Domain ID: 123_DOMAIN_COM
Registrar WHOIS Server: whois.example.com
Updated Date: 2024-01-01T00:00:00Z
Creation Date: 2000-01-01T00:00:00Z
Registrar: Example Registrar
Domain Status: ok
Name Server: NS1.GOOGLE.COM
Name Server: NS2.GOOGLE.COM
```
