/**
 * Alerts Page Logic
 */

let currentFilter = 'all';

document.addEventListener('DOMContentLoaded', async () => {
    // Set up filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentFilter = e.target.getAttribute('data-filter');
            loadAnomalies();
        });
    });
    
    // Load initial data
    await loadAnomalies();
    await loadCorrelatedAnomalies();
    
    // Refresh every 30 seconds
    setInterval(loadAnomalies, 30000);
    setInterval(loadCorrelatedAnomalies, 30000);
});

async function loadAnomalies() {
    try {
        const anomalies = await API.getAnomalies(0, 100);
        const stats = await API.getAnomalyStats();
        
        if (stats) {
            document.getElementById('high-count').textContent = stats.high_severity;
            document.getElementById('medium-count').textContent = stats.medium_severity;
            document.getElementById('low-count').textContent = stats.low_severity;
            document.getElementById('anomaly-rate').textContent = stats.anomaly_rate.toFixed(2);
        }
        
        const tbody = document.getElementById('anomalies-table');
        
        if (!anomalies || anomalies.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No anomalies detected</td></tr>';
            return;
        }
        
        // Filter anomalies
        let filtered = anomalies;
        if (currentFilter !== 'all') {
            filtered = anomalies.filter(a => a.severity === currentFilter);
        }
        
        tbody.innerHTML = filtered.map(anomaly => `
            <tr>
                <td>${UI.formatTime(anomaly.timestamp)}</td>
                <td>${anomaly.metric}</td>
                <td>${UI.formatAgentName(anomaly.agent)}</td>
                <td>${anomaly.actual_value.toFixed(2)}</td>
                <td>${anomaly.expected_value ? anomaly.expected_value.toFixed(2) : 'N/A'}</td>
                <td>${anomaly.z_score.toFixed(2)}</td>
                <td><span class="severity-badge ${anomaly.severity}">${anomaly.severity}</span></td>
                <td>${Math.round(anomaly.confidence)}%</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading anomalies:', error);
    }
}

async function loadCorrelatedAnomalies() {
    try {
        const correlated = await API.getCorrelatedAnomalies(0, 50);
        const tbody = document.getElementById('correlated-table');
        
        if (!correlated || correlated.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No correlated anomalies</td></tr>';
            return;
        }
        
        tbody.innerHTML = correlated.map(item => `
            <tr>
                <td>${UI.formatTime(item.timestamp)}</td>
                <td>${item.agents_involved.join(', ')}</td>
                <td>${item.anomaly_count}</td>
                <td>${(item.correlation_score * 100).toFixed(1)}%</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading correlated anomalies:', error);
    }
}
