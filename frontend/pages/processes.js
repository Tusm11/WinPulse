/**
 * Processes Page Logic
 */

document.addEventListener('DOMContentLoaded', async () => {
    await loadProcessData();
    setInterval(loadProcessData, 30000);
});

async function loadProcessData() {
    try {
        const metrics = await API.getLatestMetrics();
        
        if (!metrics) return;
        
        // Filter process-related metrics
        const cpuMetrics = metrics.filter(m => m.agent === 'process_resource' && m.metric === 'cpu_percent');
        const memoryMetrics = metrics.filter(m => m.agent === 'process_resource' && m.metric === 'memory_percent');
        const diskMetrics = metrics.filter(m => m.agent === 'process_resource' && m.metric === 'disk_io');
        const batteryMetrics = metrics.filter(m => m.agent === 'process_resource' && m.metric === 'battery_percent');
        
        // Update CPU
        if (cpuMetrics.length > 0) {
            const cpuValue = cpuMetrics[0].value;
            document.getElementById('cpu-value').textContent = `${cpuValue.toFixed(1)}%`;
            drawSimpleGauge('cpu-chart', cpuValue, 100);
        }
        
        // Update Memory
        if (memoryMetrics.length > 0) {
            const memValue = memoryMetrics[0].value;
            document.getElementById('memory-value').textContent = `${memValue.toFixed(1)}%`;
            drawSimpleGauge('memory-chart', memValue, 100);
        }
        
        // Update Disk I/O
        if (diskMetrics.length > 0) {
            const diskValue = diskMetrics[0].value;
            document.getElementById('disk-value').textContent = `${diskValue.toFixed(1)} MB/s`;
            drawSimpleGauge('disk-chart', diskValue, 500);
        }
        
        // Update Battery
        if (batteryMetrics.length > 0) {
            const batteryValue = batteryMetrics[0].value;
            document.getElementById('battery-value').textContent = `${batteryValue.toFixed(1)}%`;
            document.getElementById('battery-fill').style.width = batteryValue + '%';
        }
        
        // Load anomalies
        const anomalies = await API.getAnomalies(0, 50);
        const processAnomalies = anomalies.filter(a => a.agent === 'process_resource');
        
        const tbody = document.getElementById('process-anomalies');
        if (processAnomalies.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No process anomalies</td></tr>';
        } else {
            tbody.innerHTML = processAnomalies.slice(0, 10).map(a => `
                <tr>
                    <td>${UI.formatTime(a.timestamp)}</td>
                    <td>${a.metadata?.process_name || 'Unknown'}</td>
                    <td>${a.metric}</td>
                    <td>${a.actual_value.toFixed(2)}</td>
                    <td><span class="severity-badge ${a.severity}">${a.severity}</span></td>
                </tr>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading process data:', error);
    }
}

function drawSimpleGauge(canvasId, value, max) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    // Clear
    ctx.fillStyle = '#1e293b';
    ctx.fillRect(0, 0, width, height);
    
    // Draw background bar
    ctx.fillStyle = '#334155';
    ctx.fillRect(10, height - 20, width - 20, 10);
    
    // Draw value bar
    const percentage = (value / max) * 100;
    const barWidth = ((width - 20) * percentage) / 100;
    
    if (percentage < 50) {
        ctx.fillStyle = '#10b981';
    } else if (percentage < 80) {
        ctx.fillStyle = '#f59e0b';
    } else {
        ctx.fillStyle = '#ef4444';
    }
    
    ctx.fillRect(10, height - 20, barWidth, 10);
    
    // Draw text
    ctx.fillStyle = '#f1f5f9';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${value.toFixed(1)}%`, width / 2, 15);
}
