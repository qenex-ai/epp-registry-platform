# Quick Start Guide

## Installation

### Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/qenex/epp-registry-platform.git
cd epp-registry-platform

# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

Services will be available at:
- EPP Server: `localhost:700`
- RDAP API: `http://localhost:8080`
- WHOIS: `localhost:43`
- Admin Dashboard: `http://localhost:3000`

### Using Kubernetes

```bash
# Apply the deployment
kubectl apply -f k8s-deployment.yaml

# Check pods
kubectl get pods -n registry

# Port forward to access services
kubectl port-forward -n registry svc/epp-service 700:700
kubectl port-forward -n registry svc/rdap-service 8080:8080
```

## First Steps

### 1. Initialize the Database

```bash
# Connect to database container
docker exec -it registry-db psql -U registry_user -d registry

# Run schema
\i /docker-entrypoint-initdb.d/schema.sql
```

### 2. Create a Registrar Account

```python
from src.epp_server import EPPServer
import socket

# Connect
sock = socket.socket()
sock.connect(('localhost', 700))

# Login
login_cmd = '''
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <login>
      <clID>REGISTRAR1</clID>
      <pw>password123</pw>
      <options>
        <version>1.0</version>
        <lang>en</lang>
      </options>
      <svcs>
        <objURI>urn:ietf:params:xml:ns:domain-1.0</objURI>
      </svcs>
    </login>
  </command>
</epp>
'''
```

### 3. Register Your First Domain

```bash
# Using the test client
python src/epp_test_client.py --host localhost --port 700 \
  --registrar REGISTRAR1 --password password123 \
  --action register --domain example.com
```

### 4. Query via RDAP

```bash
curl http://localhost:8080/domain/example.com
```

## Configuration

### Environment Variables

Create a `.env` file:

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=registry
DB_USER=registry_user
DB_PASSWORD=your_secure_password

# EPP Server
EPP_PORT=700
EPP_TLS_CERT=/path/to/cert.pem
EPP_TLS_KEY=/path/to/key.pem

# RDAP
RDAP_PORT=8080
RDAP_BASE_URL=https://rdap.example.com

# WHOIS
WHOIS_PORT=43
```

### TLS Certificates

Generate self-signed certs for testing:

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

## Testing

```bash
# Run unit tests
pytest src/test_*.py

# Test EPP connectivity
python src/epp_test_client.py --host localhost --port 700 --action hello

# Test RDAP
curl http://localhost:8080/help

# Test WHOIS
whois -h localhost example.com
```

## Production Deployment

### Security Checklist

- [ ] Use production-grade PostgreSQL with replication
- [ ] Configure TLS with valid certificates
- [ ] Set strong database passwords
- [ ] Enable firewall rules (allow only ports 700, 43, 8080)
- [ ] Configure DNSSEC
- [ ] Set up monitoring and alerting
- [ ] Enable audit logging
- [ ] Implement rate limiting
- [ ] Configure backup strategy

### Scaling

```bash
# Scale EPP servers
docker-compose up -d --scale epp-server=5

# Or in Kubernetes
kubectl scale deployment epp-server --replicas=5 -n registry
```

## Troubleshooting

### Connection Refused

Check if services are running:
```bash
docker-compose ps
netstat -tuln | grep -E '700|43|8080'
```

### Database Connection Error

Verify credentials:
```bash
docker exec -it registry-db psql -U registry_user -d registry -c "SELECT 1"
```

### TLS Handshake Failed

Check certificate validity:
```bash
openssl s_client -connect localhost:700 -showcerts
```

## Next Steps

- Read the [Architecture Guide](docs/ARCHITECTURE.md)
- Explore the [API Documentation](docs/API.md)
- Join our [Community Forum](https://github.com/qenex/epp-registry-platform/discussions)
- Contribute! See [CONTRIBUTING.md](CONTRIBUTING.md)
