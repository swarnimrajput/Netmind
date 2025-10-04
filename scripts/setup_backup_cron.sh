#!/bin/bash

# Setup automated backups
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANSIBLE_DIR="$(dirname "$SCRIPT_DIR")/ansible"

# Create backup script
cat > /tmp/ansible_backup.sh << EOF
#!/bin/bash
cd "$ANSIBLE_DIR"
ansible-playbook -i netbox_inventory.yml playbooks/scheduled_backup.yml >> ../logs/backup.log 2>&1
EOF

chmod +x /tmp/ansible_backup.sh
sudo mv /tmp/ansible_backup.sh /usr/local/bin/

# Add cron job for daily backups at 2 AM
(crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/ansible_backup.sh") | crontab -

# Add cron job for weekly full backup at 3 AM Sundays
(crontab -l 2>/dev/null; echo "0 3 * * 0 /usr/local/bin/ansible_backup.sh") | crontab -

echo "✅ Automated backups configured:"
echo "   - Daily at 2:00 AM"
echo "   - Weekly full backup on Sundays at 3:00 AM"
echo "   - 30-day retention policy"
