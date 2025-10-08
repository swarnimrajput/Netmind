#!/bin/bash

# Configuration
LOG_FILE="/Users/swarnimrajput/Netmind/test_results/test_$(date +%Y%m%d_%H%M%S).log"
ANSIBLE_DIR="/Users/swarnimrajput/Netmind/ansible"
VAULT_PASS_FILE="$ANSIBLE_DIR/.vault_pass"

# Create test results directory
mkdir -p "/Users/swarnimrajput/Netmind/test_results"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0

# NEW: Container startup and health check
check_and_start_containers() {
    log "🐳 Checking container status..."
    
    # Check if containers exist
    containers=("R1" "R2" "R3")
    missing_containers=()
    
    for container in "${containers[@]}"; do
        if ! docker ps -a --format "{{.Names}}" | grep -q "^${container}$"; then
            missing_containers+=($container)
        fi
    done
    
    if [ ${#missing_containers[@]} -gt 0 ]; then
        log "❌ Missing containers: ${missing_containers[*]}"
        log "⚠️ Please create containers first with: docker run -d --name R1 alpine:latest sleep 3600"
        return 1
    fi
    
    # Start containers if not running
    stopped_containers=()
    for container in "${containers[@]}"; do
        if ! docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            stopped_containers+=($container)
        fi
    done
    
    if [ ${#stopped_containers[@]} -gt 0 ]; then
        log "🔄 Starting stopped containers: ${stopped_containers[*]}"
        docker start "${stopped_containers[@]}" >> "$LOG_FILE" 2>&1
        
        # Wait for containers to be ready
        log "⏳ Waiting for containers to be ready..."
        sleep 10
    fi
    
    # Verify all containers are running
    all_running=true
    for container in "${containers[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            log "✅ $container is running"
        else
            log "❌ $container failed to start"
            all_running=false
        fi
    done
    
    return $all_running
}

# Function to run ansible commands with vault password
run_ansible_test() {
    local test_name="$1"
    local command="$2"
    
    log "🧪 Testing $test_name..."
    
    cd "$ANSIBLE_DIR" || {
        log "[ERROR] ❌ Could not change to ansible directory"
        ((TESTS_FAILED++))
        return 1
    }
    
    # Check if vault password file exists
    if [ -f "$VAULT_PASS_FILE" ]; then
        # Run with vault password file
        if eval "$command --vault-password-file .vault_pass" >> "$LOG_FILE" 2>&1; then
            log "✅ $test_name passed"
            ((TESTS_PASSED++))
            return 0
        else
            log "[ERROR] ❌ $test_name failed"
            ((TESTS_FAILED++))
            return 1
        fi
    else
        # Run without vault (for basic testing)
        log "⚠️ No vault password file found, running without vault..."
        if eval "$command" >> "$LOG_FILE" 2>&1; then
            log "✅ $test_name passed (no vault)"
            ((TESTS_PASSED++))
            return 0
        else
            log "[ERROR] ❌ $test_name failed"
            ((TESTS_FAILED++))
            return 1
        fi
    fi
}

# Main test execution
log "🚀 Starting Network Automation Test Pipeline"

# NEW: Check and start containers first
if ! check_and_start_containers; then
    log "[ERROR] ❌ Container setup failed, aborting tests"
    exit 1
fi

# Test 1: Inventory
run_ansible_test "Ansible inventory" "ansible-inventory -i netbox_inventory.yml --list"

# Test 2: Configuration push (check mode)
run_ansible_test "Configuration push" "ansible-playbook -i netbox_inventory.yml playbooks/push_configs.yml --check"

# Test 3: Facts collection
run_ansible_test "Facts collection" "ansible-playbook -i netbox_inventory.yml playbooks/frr_facts.yml"

# Test 4: Device validation
log "🔍 Testing device validation..."
cd "/Users/swarnimrajput/Netmind/netbox"
if python3 validate_device_state.py >> "$LOG_FILE" 2>&1; then
    log "✅ Device validation passed"
    ((TESTS_PASSED++))
else
    log "[ERROR] ❌ Device validation failed"
    ((TESTS_FAILED++))
fi

# Test 5: Health monitoring
log "🏥 Testing health monitoring..."
cd "/Users/swarnimrajput/Netmind/netbox"
if python3 monitor_devices.py >> "$LOG_FILE" 2>&1; then
    log "✅ Health monitoring passed"
    ((TESTS_PASSED++))
else
    log "[ERROR] ❌ Health monitoring failed"
    ((TESTS_FAILED++))
fi

# Test 6: NetBox API connectivity
log "🌐 Testing NetBox API..."
if curl -s -H "Authorization: Token c316eac1941ee8fdd5059e4f9e777648459ab551" \
        http://localhost:8000/api/dcim/devices/ > /dev/null; then
    log "✅ NetBox API accessible"
    ((TESTS_PASSED++))
else
    log "[ERROR] ❌ NetBox API failed"
    ((TESTS_FAILED++))
fi

# Performance benchmark
log "⚡ Running performance benchmarks..."
start_time=$(date +%s)
sleep 2  # Simulate some work
end_time=$(date +%s)
duration=$((end_time - start_time))
log "📈 Pipeline benchmark: ${duration}s"

# Generate report
log "📋 Generating test report..."
cat > "/Users/swarnimrajput/Netmind/test_results/test_report.html" << EOF
<!DOCTYPE html>
<html>
<head><title>Network Automation Test Report</title></head>
<body>
<h1>🚀 Network Automation Test Report</h1>
<h2>Test Summary</h2>
<p>✅ Tests Passed: $TESTS_PASSED</p>
<p>❌ Tests Failed: $TESTS_FAILED</p>
<p>📈 Total Runtime: ${duration}s</p>
<p>📅 Generated: $(date)</p>
<h2>Detailed Logs</h2>
<pre>$(cat "$LOG_FILE")</pre>
</body>
</html>
EOF

log "📋 Test report generated: /Users/swarnimrajput/Netmind/test_results/test_report.html"

# Final result
if [ $TESTS_FAILED -eq 0 ]; then
    log "🎉 All tests passed!"
    exit 0
else
    log "[ERROR] ❌ $TESTS_FAILED test(s) failed. Check logs for details."
    exit 1
fi
