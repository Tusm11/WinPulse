/**
 * Applications Page Logic
 */

document.addEventListener('DOMContentLoaded', async () => {
    await loadApplicationData();
    setInterval(loadApplicationData, 30000);
});

async function loadApplicationData() {
    try {
        const metrics = await API.getLatestMetrics();
        
        if (!metrics) return;
        
        // Filter application metrics
        const userMetrics = metrics.filter(m => m.agent === 'session' && m.metric === 'active_users');
        const focusMetrics = metrics.filter(m => m.agent === 'application' && m.metric === 'app_focus_duration');
        const loginMetrics = metrics.filter(m => m.agent === 'session' && m.metric === 'login');
        
        // Update Active Users
        if (userMetrics.length > 0) {
            const userCount = userMetrics[0].value;
            document.getElementById('active-users').textContent = Math.round(userCount);
            const users = userMetrics[0].metadata?.users || [];
            document.getElementById('users-list').textContent = users.join(', ') || 'No users';
        }
        
        // Update Focus Time
        if (focusMetrics.length > 0) {
            const focusValue = focusMetrics[0].value;
            document.getElementById('focus-value').textContent = formatDuration(focusValue);
        }
        
        // Update Login Count
        if (loginMetrics.length > 0) {
            document.getElementById('login-count').textContent = loginMetrics.length;
        }
        
        // Load anomalies
        const anomalies = await API.getAnomalies(0, 50);
        const appAnomalies = anomalies.filter(a => a.agent === 'application' || a.agent === 'session');
        
        const tbody = document.getElementById('app-anomalies');
        if (appAnomalies.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No application anomalies</td></tr>';
        } else {
            tbody.innerHTML = appAnomalies.slice(0, 10).map(a => `
                <tr>
                    <td>${UI.formatTime(a.timestamp)}</td>
                    <td>${a.metadata?.window_title || a.metadata?.app || 'Unknown'}</td>
                    <td>${a.metric}</td>
                    <td>${formatDuration(a.actual_value)}</td>
                    <td><span class="severity-badge ${a.severity}">${a.severity}</span></td>
                </tr>
            `).join('');
        }
        
        // Load login history
        const loginHistory = anomalies.filter(a => 
            (a.metric === 'login' || a.metric === 'logout') && a.agent === 'session'
        );
        
        const historyTbody = document.getElementById('login-history');
        if (loginHistory.length === 0) {
            historyTbody.innerHTML = '<tr><td colspan="4" class="empty-state">No login events</td></tr>';
        } else {
            historyTbody.innerHTML = loginHistory.slice(0, 10).map(a => `
                <tr>
                    <td>${UI.formatTime(a.timestamp)}</td>
                    <td>${a.metadata?.username || 'Unknown'}</td>
                    <td>${a.metric === 'login' ? 'Login' : 'Logout'}</td>
                    <td>${a.metadata?.terminal || 'Console'}</td>
                </tr>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading application data:', error);
    }
}

function formatDuration(seconds) {
    if (seconds < 60) {
        return `${Math.round(seconds)}s`;
    } else if (seconds < 3600) {
        return `${Math.round(seconds / 60)}m`;
    } else {
        return `${Math.round(seconds / 3600)}h`;
    }
}
