/**
 * Network Page Logic
 */

document.addEventListener('DOMContentLoaded', async () => {
    await loadNetworkData();
    setInterval(loadNetworkData, 30000);
});

async function loadNetworkData() {
    try {
        const metrics = await API.getLatestMetrics();
        
        if (!metrics) return;
        
        // Filter network metrics
        const sentMetrics = metrics.filter(m => m.agent === 'network' && m.metric === 'bytes_sent');
        const receivedMetrics = metrics.filter(m => m.agent === 'network' && m.metric === 'bytes_received');
        const connMetrics = metrics.filter(m => m.agent === 'network' && m.metric === 'active_connections');
        
        // Update Bytes Sent
        if (sentMetrics.length > 0) {
            const sentValue = sentMetrics[0].value;
            document.getElementById('sent-value').textContent = formatBytes(sentValue);
            drawSimpleChart('sent-chart', sentValue, 1000000);
        }
        
        // Update Bytes Received
        if (receivedMetrics.length > 0) {
            const recValue = receivedMetrics[0].value;
            document.getElementById('received-value').textContent = formatBytes(recValue);
            drawSimpleChart('received-chart', recValue, 1000000);
        }
        
        // Update Connections
        if (connMetrics.length > 0) {
            const connValue = connMetrics[0].value;
            document.getElementById('connection-count').textContent = Math.round(connValue);
        }
        
        // Load anomalies
        const anomalies = await API.getAnomalies(0, 50);
        const networkAnomalies = anomalies.filter(a => a.agent === 'network');
        
        const tbody = document.getElementById('network-anomalies');
        if (networkAnomalies.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No network anomalies</td></tr>';
        } else {
            tbody.innerHTML = networkAnomalies.slice(0, 10).map(a => `
                <tr>
                    <td>${UI.formatTime(a.timestamp)}</td>
                    <td>${a.metadata?.process_name || 'Unknown'}</td>
                    <td>${a.metadata?.remote_ip || 'N/A'}</td>
                    <td>${a.metadata?.port || 'N/A'}</td>
                    <td>${formatBytes(a.actual_value)}</td>
                    <td><span class="severity-badge ${a.severity}">${a.severity}</span></td>
                </tr>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading network data:', error);
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
}

function drawSimpleChart(canvasId, value, max) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    // Clear
    ctx.fillStyle = '#1e293b';
    ctx.fillRect(0, 0, width, height);
    
    // Draw bar
    const percentage = Math.min((value / max) * 100, 100);
    const barHeight = (height - 30) * (percentage / 100);
    
    if (percentage < 50) {
        ctx.fillStyle = '#10b981';
    } else if (percentage < 80) {
        ctx.fillStyle = '#f59e0b';
    } else {
        ctx.fillStyle = '#ef4444';
    }
    
    ctx.fillRect(width / 2 - 20, height - 20 - barHeight, 40, barHeight);
    
    // Draw text
    ctx.fillStyle = '#f1f5f9';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${percentage.toFixed(0)}%`, width / 2, 15);
}
