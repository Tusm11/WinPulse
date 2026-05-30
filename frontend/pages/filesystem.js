/**
 * File System Page Logic
 */

document.addEventListener('DOMContentLoaded', async () => {
    await loadFileSystemData();
    setInterval(loadFileSystemData, 30000);
});

async function loadFileSystemData() {
    try {
        const metrics = await API.getLatestMetrics();
        
        if (!metrics) return;
        
        // Filter filesystem metrics
        const createdMetrics = metrics.filter(m => m.agent === 'filesystem' && m.metric === 'file_created');
        const modifiedMetrics = metrics.filter(m => m.agent === 'filesystem' && m.metric === 'file_modified');
        const deletedMetrics = metrics.filter(m => m.agent === 'filesystem' && m.metric === 'file_deleted');
        const usbMetrics = metrics.filter(m => m.agent === 'device' && m.metric === 'usb_mount');
        
        // Update counts
        document.getElementById('files-created').textContent = createdMetrics.length;
        document.getElementById('files-modified').textContent = modifiedMetrics.length;
        document.getElementById('files-deleted').textContent = deletedMetrics.length;
        document.getElementById('usb-count').textContent = usbMetrics.length;
        
        // Load anomalies
        const anomalies = await API.getAnomalies(0, 50);
        const fsAnomalies = anomalies.filter(a => a.agent === 'filesystem');
        
        const tbody = document.getElementById('fs-anomalies');
        if (fsAnomalies.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No file system anomalies</td></tr>';
        } else {
            tbody.innerHTML = fsAnomalies.slice(0, 10).map(a => `
                <tr>
                    <td>${UI.formatTime(a.timestamp)}</td>
                    <td>${a.metric === 'file_created' ? 'Created' : a.metric === 'file_modified' ? 'Modified' : 'Deleted'}</td>
                    <td>${a.metadata?.path || 'Unknown'}</td>
                    <td>${a.metadata?.size ? formatBytes(a.metadata.size) : 'N/A'}</td>
                    <td><span class="severity-badge ${a.severity}">${a.severity}</span></td>
                </tr>
            `).join('');
        }
        
        // Load USB activity
        const deviceAnomalies = anomalies.filter(a => a.agent === 'device');
        
        const usbTbody = document.getElementById('usb-activity');
        if (deviceAnomalies.length === 0) {
            usbTbody.innerHTML = '<tr><td colspan="4" class="empty-state">No USB activity</td></tr>';
        } else {
            usbTbody.innerHTML = deviceAnomalies.slice(0, 10).map(a => `
                <tr>
                    <td>${UI.formatTime(a.timestamp)}</td>
                    <td>${a.metadata?.device_name || 'Unknown Device'}</td>
                    <td>${a.metric === 'usb_mount' ? 'Mounted' : 'Unmounted'}</td>
                    <td>${a.metadata?.drive_letter || 'N/A'}</td>
                </tr>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading file system data:', error);
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
}
