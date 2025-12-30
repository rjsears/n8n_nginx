# Troubleshooting Guide

This guide covers common issues and their solutions for n8n_nginx v3.0.

---

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Container Issues](#container-issues)
3. [Database Issues](#database-issues)
4. [SSL/Certificate Issues](#sslcertificate-issues)
5. [Network Issues](#network-issues)
6. [Backup Issues](#backup-issues)
7. [Management Console Issues](#management-console-issues)

### Other Documentation

- [API Reference](./API.md) - REST API documentation
- [Backup Guide](./BACKUP_GUIDE.md) - Backup and restore procedures
- [Certbot Guide](./CERTBOT.md) - SSL certificate management
- [Cloudflare Guide](./CLOUDFLARE.md) - Cloudflare Tunnel setup
- [Migration Guide](./MIGRATION.md) - Upgrading from v2.0 to v3.0
- [Notifications Guide](./NOTIFICATIONS.md) - Alert and notification setup
- [Tailscale Guide](./TAILSCALE.md) - Tailscale VPN integration

---

## Quick Diagnostics

Run these commands first to understand the current state:

```bash
# Check all container status
docker compose ps

# Run health check
./scripts/health_check.sh

# View recent logs
docker compose logs --tail 50

# Check disk space
df -h

# Check memory
free -h
```

---

## Container Issues

### Container Won't Start

**Symptoms:** Container shows "Exited" or keeps restarting

**Diagnosis:**
```bash
# Check container logs
docker logs <container_name> --tail 100

# Check if container exists
docker compose ps -a

# Inspect container
docker inspect <container_name>
```

**Common Solutions:**

1. **Port conflict:**
   ```bash
   # Find what's using the port
   sudo netstat -tlpn | grep <port>
   # or
   sudo ss -tlpn | grep <port>

   # Change port in .env and restart
   ```

2. **Volume permission issues:**
   ```bash
   # Check volume permissions
   docker volume inspect <volume_name>

   # Fix ownership (if needed)
   docker exec <container> chown -R <user>:<group> /path
   ```

3. **Missing environment variables:**
   ```bash
   # Check .env file exists and has required vars
   cat .env

   # Regenerate if needed
   ./setup.sh
   ```

### Container Health Check Failing

**Symptoms:** Container shows "unhealthy"

**Diagnosis:**
```bash
# Check health status details
docker inspect --format='{{json .State.Health}}' <container_name> | jq

# Check what health check is doing
docker inspect --format='{{json .Config.Healthcheck}}' <container_name> | jq
```

**Solutions by Container:**

**n8n:**
```bash
# Check n8n can respond
docker exec n8n curl -s http://localhost:5678/healthz

# Check database connection
docker exec n8n curl -s http://localhost:5678/healthz/db
```

**PostgreSQL:**
```bash
# Check PostgreSQL is ready
docker exec n8n_postgres pg_isready -U n8n

# Check PostgreSQL logs
docker logs n8n_postgres --tail 50
```

**Management:**
```bash
# Check API responds
docker exec n8n_management curl -s http://localhost:8000/api/health

# Check database connection
docker exec n8n_management python -c "from core.database import engine; print(engine.url)"
```

---

## Network & Connectivity

### Can't Access n8n

**Symptoms:** Browser shows timeout or connection refused

**Diagnosis:**
```bash
# Test from server
curl -k https://localhost/healthz

# Test nginx
docker exec n8n_nginx nginx -t

# Check ports are listening
ss -tlpn | grep -E ':(80|443)'
```

**Solutions:**

1. **Check nginx is running:**
   ```bash
   docker compose ps nginx
   docker compose restart nginx
   ```

2. **Check firewall:**
   ```bash
   # UFW
   sudo ufw status
   sudo ufw allow 443/tcp

   # firewalld
   sudo firewall-cmd --list-ports
   sudo firewall-cmd --add-port=443/tcp --permanent
   ```

3. **Check DNS resolution:**
   ```bash
   dig your-domain.com
   nslookup your-domain.com
   ```

### Can't Access Management Console

**Symptoms:** Management console doesn't respond

**Solutions:**

1. **Check nginx is running:**
   ```bash
   docker ps | grep n8n_nginx
   ```

2. **Check management container is running:**
   ```bash
   docker ps | grep n8n_management
   ```

3. **Verify nginx config has management location block:**
   ```bash
   docker exec n8n_nginx cat /etc/nginx/nginx.conf | grep -A 10 "location /management"
   ```

4. **Restart nginx:**
   ```bash
   docker compose restart nginx
   ```

### 502 Bad Gateway

**Symptoms:** Nginx returns 502 error

**Cause:** Backend service is down or unreachable

**Solutions:**

1. **Check backend is running:**
   ```bash
   # For n8n
   docker compose ps n8n
   docker logs n8n --tail 50

   # For management
   docker compose ps n8n_management
   docker logs n8n_management --tail 50
   ```

2. **Check backend is healthy:**
   ```bash
   # n8n
   docker exec n8n curl -s http://localhost:5678/healthz

   # Management
   docker exec n8n_management curl -s http://localhost:8000/api/health
   ```

3. **Restart services:**
   ```bash
   docker compose restart n8n n8n_management nginx
   ```

---

## Database Issues

### PostgreSQL Won't Start

**Symptoms:** postgres container exits or won't become healthy

**Diagnosis:**
```bash
docker logs n8n_postgres --tail 100
```

**Solutions:**

1. **Disk space:**
   ```bash
   df -h
   # Clean up if needed
   docker system prune -f
   ```

2. **Corrupted data:**
   ```bash
   # Warning: This will lose data if no backup
   docker volume rm n8n_postgres_data
   docker compose up -d postgres
   ```

3. **Permission issues:**
   ```bash
   docker exec n8n_postgres ls -la /var/lib/postgresql/data
   ```

### Can't Connect to Database

**Symptoms:** "Connection refused" or authentication errors

**Diagnosis:**
```bash
# Check PostgreSQL is ready
docker exec n8n_postgres pg_isready -U n8n

# Check from n8n container
docker exec n8n ping -c 1 n8n_postgres

# Test authentication
docker exec n8n_postgres psql -U n8n -d n8n -c "SELECT 1"
```

**Solutions:**

1. **Check password in .env:**
   ```bash
   grep POSTGRES .env
   ```

2. **Check PostgreSQL is accepting connections:**
   ```bash
   docker exec n8n_postgres cat /var/lib/postgresql/data/pg_hba.conf
   ```

3. **Restart PostgreSQL:**
   ```bash
   docker compose restart postgres
   ```

### Database Full or Slow

**Symptoms:** Slow queries, disk space errors

**Solutions:**

1. **Check database size:**
   ```bash
   docker exec n8n_postgres psql -U n8n -c "
     SELECT pg_database.datname,
            pg_size_pretty(pg_database_size(pg_database.datname)) AS size
     FROM pg_database ORDER BY pg_database_size(pg_database.datname) DESC;
   "
   ```

2. **Clean old executions:**
   ```bash
   docker exec n8n_postgres psql -U n8n -d n8n -c "
     DELETE FROM execution_entity WHERE finished_at < NOW() - INTERVAL '30 days';
   "
   ```

3. **Vacuum database:**
   ```bash
   docker exec n8n_postgres psql -U n8n -d n8n -c "VACUUM FULL;"
   ```

---

## SSL Certificate Issues

### Certificate Expired or Invalid

**Symptoms:** Browser shows certificate warning

**Diagnosis:**
```bash
# Check certificate dates
docker exec n8n_nginx openssl x509 -in /etc/letsencrypt/live/your-domain.com/cert.pem -dates -noout

# Check from outside
echo | openssl s_client -connect your-domain.com:443 2>/dev/null | openssl x509 -noout -dates
```

**Solutions:**

1. **Force renewal:**
   ```bash
   docker exec n8n_certbot certbot renew --force-renewal
   docker compose restart nginx
   ```

2. **Check certbot logs:**
   ```bash
   docker logs n8n_certbot --tail 100
   ```

3. **Verify DNS credentials:**
   ```bash
   cat cloudflare.ini  # or your DNS provider file
   ```

### Certificate Not Found

**Symptoms:** "Certificate not found" errors

**Solutions:**

1. **Check certificate exists:**
   ```bash
   docker exec n8n_nginx ls -la /etc/letsencrypt/live/
   ```

2. **Check Let's Encrypt volume:**
   ```bash
   docker volume inspect letsencrypt
   ```

3. **Request new certificate:**
   ```bash
   docker exec n8n_certbot certbot certonly \
     --dns-cloudflare \
     --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
     -d your-domain.com
   ```

---

## Backup Issues

### Backup Fails

**Symptoms:** Backup shows "failed" status

**Diagnosis:**
```bash
# Check management logs
docker logs n8n_management --tail 100 | grep -i backup

# Check disk space
df -h
```

**Solutions:**

1. **PostgreSQL connection:**
   ```bash
   docker exec n8n_management pg_isready -h postgres -U n8n
   ```

2. **Disk space:**
   ```bash
   # Clean old backups
   # Via UI or:
   docker exec n8n_management rm /app/backups/old_backup.dump
   ```

3. **NFS issues:**
   ```bash
   docker exec n8n_management mount | grep nfs
   docker exec n8n_management df -h /mnt/nfs
   ```

### NFS Mount Issues

**Symptoms:** NFS shows disconnected

**Diagnosis:**
```bash
# Test NFS server
showmount -e nfs-server-ip

# Test mount
docker exec n8n_management mount -t nfs nfs-server:/path /mnt/test
```

**Solutions:**

1. **Check network:**
   ```bash
   docker exec n8n_management ping -c 1 nfs-server-ip
   docker exec n8n_management nc -zv nfs-server-ip 2049
   ```

2. **Check exports on NFS server:**
   ```bash
   # On NFS server
   cat /etc/exports
   exportfs -v
   ```

3. **Remount:**
   ```bash
   docker compose restart n8n_management
   ```

---

## Authentication Issues

### Can't Log In to Management Console

**Symptoms:** Login fails with valid credentials

**Solutions:**

1. **Reset password via CLI:**
   ```bash
   docker exec n8n_management python -c "
   from core.database import SessionLocal
   from models.user import User
   from core.security import get_password_hash

   db = SessionLocal()
   user = db.query(User).filter(User.username == 'admin').first()
   user.hashed_password = get_password_hash('new-password-here')
   db.commit()
   print('Password updated')
   "
   ```

2. **Check user exists:**
   ```bash
   docker exec n8n_postgres psql -U n8n -d n8n_management -c "SELECT username, email FROM users;"
   ```

3. **Clear sessions:**
   ```bash
   docker compose restart n8n_management
   ```

### Session Expires Too Quickly

**Solution:**
```bash
# Adjust session timeout in settings
# Via UI: Settings → Security → Session Timeout
# Or via API:
curl -X PUT https://your-domain.com/management/api/settings \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"session_timeout_hours": 48}'
```

---

## Performance Issues

### High CPU Usage

**Diagnosis:**
```bash
docker stats
top
```

**Solutions:**

1. **Identify culprit container:**
   ```bash
   docker stats --no-stream
   ```

2. **Check for runaway workflows:**
   - Open n8n UI
   - Check Executions for stuck jobs
   - Disable problematic workflows

3. **Limit container resources:**
   ```yaml
   # In docker-compose.yaml
   services:
     n8n:
       deploy:
         resources:
           limits:
             cpus: '2'
   ```

### High Memory Usage

**Diagnosis:**
```bash
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}"
free -h
```

**Solutions:**

1. **Increase swap:**
   ```bash
   sudo fallocate -l 4G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

2. **Limit container memory:**
   ```yaml
   services:
     n8n:
       deploy:
         resources:
           limits:
             memory: 2G
   ```

3. **Clean execution data:**
   ```bash
   # Via n8n settings or:
   docker exec n8n_postgres psql -U n8n -d n8n -c "
     DELETE FROM execution_entity WHERE finished_at < NOW() - INTERVAL '7 days';
   "
   ```

### Slow Workflows

**Solutions:**

1. **Check database performance:**
   ```bash
   docker exec n8n_postgres psql -U n8n -d n8n -c "
     SELECT * FROM pg_stat_activity WHERE state = 'active';
   "
   ```

2. **Add database indexes:**
   ```bash
   docker exec n8n_postgres psql -U n8n -d n8n -c "
     CREATE INDEX IF NOT EXISTS idx_execution_workflow ON execution_entity(workflow_id);
   "
   ```

3. **Vacuum database:**
   ```bash
   docker exec n8n_postgres psql -U n8n -d n8n -c "VACUUM ANALYZE;"
   ```

---

## Logs & Debugging

### View All Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f n8n
docker compose logs -f n8n_management
docker compose logs -f nginx

# Last N lines
docker compose logs --tail 100 n8n
```

### Enable Debug Logging

**n8n:**
```bash
# Add to .env
N8N_LOG_LEVEL=debug

# Restart
docker compose restart n8n
```

**Management:**
```bash
# Add to .env
DEBUG=true

# Restart
docker compose restart n8n_management
```

### Export Logs for Support

```bash
# Create support bundle
mkdir -p support-bundle
docker compose logs > support-bundle/docker-logs.txt
docker compose ps > support-bundle/container-status.txt
./scripts/health_check.sh > support-bundle/health-check.txt 2>&1
df -h > support-bundle/disk-usage.txt
free -h > support-bundle/memory-usage.txt
docker stats --no-stream > support-bundle/container-stats.txt

# Create archive
tar -czf support-bundle.tar.gz support-bundle/
```

---

## Getting More Help

If you can't resolve the issue:

1. **Search existing issues:**
   https://github.com/rjsears/n8n_nginx/issues

2. **Create new issue with:**
   - Operating system and version
   - Docker and Docker Compose versions
   - Full error messages
   - Relevant log excerpts
   - Steps to reproduce

3. **Community resources:**
   - n8n Community: https://community.n8n.io
   - Discord: https://discord.gg/n8n
