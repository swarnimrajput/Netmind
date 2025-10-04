#!/bin/bash

echo "🔗 Testing container connectivity..."

# Check if containers are running
containers=("R1" "R2" "R3")
all_running=true

for container in "${containers[@]}"; do
    if docker ps --format "table {{.Names}}" | grep -q "^$container$"; then
        echo "✅ $container is running"
    else
        echo "❌ $container is not running"
        all_running=false
    fi
done

if [ "$all_running" = false ]; then
    echo "⚠️ Starting containers..."
    docker start R1 R2 R3 2>/dev/null || echo "Containers may have different names"
    sleep 5
fi

# Test basic connectivity
echo "🧪 Testing basic connectivity..."
for container in "${containers[@]}"; do
    if docker exec $container echo "ping" >/dev/null 2>&1; then
        echo "✅ Can connect to $container"
    else
        echo "❌ Cannot connect to $container"
        exit 1
    fi
done

echo "✅ All connectivity tests passed"
