/**
 * Main Application Logic
 */

// Initialize app on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    console.log('Initializing WinPulse Dashboard...');
    
    // Set up navigation
    setupNavigation();
    
    // Load initial data
    await loadDashboardData();
    
    // Set up auto-refresh
    setInterval(loadDashboardData, 10000); // Refresh every 10 seconds
}

function setupNavigation() {
    // Add click handlers to nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const pageName = item.getAttribute('data-page');
            UI.navigateToPage(pageName);
            
            // Load page-specific data
            loadPageData(pageName);
        });
    });
}

async function loadDashboardData() {
    try {
        // Load all dashboard data in parallel
        const [overview, stats, agents, warmup] = await Promise.all([
            API.getDashboardOverview(),
            API.getAnomalyStats(),
            API.getAgentStatus(),
            API.getWarmupProgress()
        ]);
        
        if (overview) {
            // Update risk score
            UI.updateRiskScore(overview.system_status.risk_score || 0);
            
            // Update warmup progress
            UI.updateWarmupProgress(overview.warmup_progress);
            
            // Update anomaly counts
            if (stats) {
                UI.updateAnomalyCounts(stats);
            }
            
            // Update agent status
            if (overview.agents) {
                UI.updateAgentStatus(overview.agents);
            }
            
            // Update health indicator
            UI.updateHealthIndicator(overview.system_status);
            
            // Update recent anomalies
            if (overview.recent_anomalies) {
                UI.updateRecentAnomalies(overview.recent_anomalies);
            }
        }
    } catch (error) {
        console.error('Error loading dashboard data:', error);
    }
}

async function loadPageData(pageName) {
    switch (pageName) {
        case 'processes':
            await loadProcessesPage();
            break;
        case 'network':
            await loadNetworkPage();
            break;
        case 'applications':
            await loadApplicationsPage();
            break;
        case 'filesystem':
            await loadFileSystemPage();
            break;
        case 'alerts':
            await loadAlertsPage();
            break;
    }
}

async function loadProcessesPage() {
    console.log('Loading processes page...');
    // This would load process-specific data
    // For now, just show the page
}

async function loadNetworkPage() {
    console.log('Loading network page...');
    // This would load network-specific data
}

async function loadApplicationsPage() {
    console.log('Loading applications page...');
    // This would load application-specific data
}

async function loadFileSystemPage() {
    console.log('Loading file system page...');
    // This would load file system-specific data
}

async function loadAlertsPage() {
    console.log('Loading alerts page...');
    
    try {
        const anomalies = await API.getAnomalies(0, 100);
        
        // Create alerts page if it doesn't exist
        let alertsPage = document.getElementById('alerts-page');
        if (!alertsPage) {
            alertsPage = document.createElement('section');
            alertsPage.id = 'alerts-page';
            alertsPage.className = 'page';
            document.querySelector('.content').appendChild(alertsPage);
        }
        
        // Build alerts table
        let html = `
            <div class="card">
                <h3>All Anomalies</h3>
                <div class="table-container">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Metric</th>
                                <th>Agent</th>
                                <th>Value</th>
                                <th>Expected</th>
                                <th>Z-Score</th>
                                <th>Severity</th>
                                <th>Confidence</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        
        if (anomalies && anomalies.length > 0) {
            anomalies.forEach(anomaly => {
                html += `
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
                `;
            });
        } else {
            html += '<tr><td colspan="8" class="empty-state">No anomalies detected</td></tr>';
        }
        
        html += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        
        alertsPage.innerHTML = html;
    } catch (error) {
        console.error('Error loading alerts page:', error);
    }
}

// Search functionality
document.getElementById('search-input')?.addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase();
    
    // Filter table rows
    document.querySelectorAll('.data-table tbody tr').forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
    });
});
