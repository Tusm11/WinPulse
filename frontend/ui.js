/**
 * UI Module - Handles all UI updates and interactions
 */

const UI = {
    // Update connection status indicator
    updateConnectionStatus(isConnected) {
        const statusEl = document.getElementById('connection-status');
        const dot = document.querySelector('.dot');
        
        if (isConnected) {
            statusEl.textContent = 'Connected';
            dot.classList.add('online');
            this.hideToast();
        } else {
            statusEl.textContent = 'Disconnected';
            dot.classList.remove('online');
            this.showToast('Connection lost. Reconnecting...', 'warning');
        }
    },
    
    // Show toast notification
    showToast(message, type = 'info') {
        const toast = document.getElementById('connection-toast');
        const toastMessage = document.getElementById('toast-message');
        
        toastMessage.textContent = message;
        toast.classList.remove('hidden');
        
        // Auto-hide after 5 seconds
        setTimeout(() => this.hideToast(), 5000);
    },
    
    // Hide toast notification
    hideToast() {
        const toast = document.getElementById('connection-toast');
        toast.classList.add('hidden');
    },
    
    // Update risk score gauge
    updateRiskScore(score) {
        const riskScore = document.getElementById('risk-score');
        const gaugeFill = document.getElementById('risk-gauge-fill');
        const riskStatus = document.getElementById('risk-status');
        
        riskScore.textContent = Math.round(score);
        
        // Calculate stroke-dashoffset for gauge (0-565 range)
        const offset = 565 - (score / 100) * 565;
        gaugeFill.style.strokeDashoffset = offset;
        
        // Update color based on score
        if (score < 30) {
            gaugeFill.style.stroke = '#10b981'; // Green
            riskStatus.textContent = 'Low Risk';
        } else if (score < 60) {
            gaugeFill.style.stroke = '#f59e0b'; // Orange
            riskStatus.textContent = 'Medium Risk';
        } else {
            gaugeFill.style.stroke = '#ef4444'; // Red
            riskStatus.textContent = 'High Risk';
        }
    },
    
    // Update warmup progress
    updateWarmupProgress(data) {
        if (!data) return;
        
        const progressFill = document.getElementById('warmup-progress');
        const warmupText = document.getElementById('warmup-text');
        
        const percentage = (data.days_elapsed / 7) * 100;
        progressFill.style.width = Math.min(percentage, 100) + '%';
        warmupText.textContent = `${data.days_elapsed} / 7 days`;
    },
    
    // Update anomaly count
    updateAnomalyCounts(stats) {
        if (!stats) return;
        
        const anomalyCount = document.getElementById('anomaly-count');
        const anomalyBreakdown = document.getElementById('anomaly-breakdown');
        
        anomalyCount.textContent = stats.total_anomalies;
        anomalyBreakdown.textContent = 
            `High: ${stats.high_severity} | Medium: ${stats.medium_severity} | Low: ${stats.low_severity}`;
    },
    
    // Update agent status list
    updateAgentStatus(agents) {
        if (!agents || agents.length === 0) return;
        
        const agentsList = document.getElementById('agents-list');
        agentsList.innerHTML = '';
        
        agents.forEach(agent => {
            const agentItem = document.createElement('div');
            agentItem.className = 'agent-item';
            
            const statusClass = agent.is_active ? '' : 'inactive';
            const statusSymbol = agent.is_active ? '●' : '○';
            
            agentItem.innerHTML = `
                <span class="agent-name">${this.formatAgentName(agent.agent_name)}</span>
                <span class="agent-status ${statusClass}">${statusSymbol}</span>
            `;
            
            agentsList.appendChild(agentItem);
        });
    },
    
    // Format agent name for display
    formatAgentName(name) {
        return name
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    },
    
    // Update system health indicator
    updateHealthIndicator(stats) {
        if (!stats) return;
        
        const healthDot = document.querySelector('.health-dot');
        const healthText = document.getElementById('health-text');
        
        const riskScore = stats.risk_score || 0;
        
        if (riskScore < 30) {
            healthDot.classList.remove('warning', 'danger');
            healthText.textContent = 'Good';
        } else if (riskScore < 60) {
            healthDot.classList.add('warning');
            healthDot.classList.remove('danger');
            healthText.textContent = 'Fair';
        } else {
            healthDot.classList.add('danger');
            healthDot.classList.remove('warning');
            healthText.textContent = 'Poor';
        }
    },
    
    // Update recent anomalies table
    updateRecentAnomalies(anomalies) {
        const tbody = document.getElementById('recent-anomalies');
        
        if (!anomalies || anomalies.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No anomalies detected</td></tr>';
            return;
        }
        
        tbody.innerHTML = anomalies.slice(0, 5).map(anomaly => `
            <tr>
                <td>${this.formatTime(anomaly.timestamp)}</td>
                <td>${anomaly.metric}</td>
                <td>${this.formatAgentName(anomaly.agent)}</td>
                <td><span class="severity-badge ${anomaly.severity}">${anomaly.severity}</span></td>
                <td>${Math.round(anomaly.confidence)}%</td>
            </tr>
        `).join('');
    },
    
    // Update system status
    updateSystemStatus(status) {
        if (!status) return;
        
        this.updateRiskScore(status.risk_score || 0);
        this.updateHealthIndicator(status);
    },
    
    // Format timestamp for display
    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        // Less than 1 minute
        if (diff < 60000) {
            return 'Just now';
        }
        
        // Less than 1 hour
        if (diff < 3600000) {
            const minutes = Math.floor(diff / 60000);
            return `${minutes}m ago`;
        }
        
        // Less than 1 day
        if (diff < 86400000) {
            const hours = Math.floor(diff / 3600000);
            return `${hours}h ago`;
        }
        
        // Format as time
        return date.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit',
            hour12: true 
        });
    },
    
    // Update current time in header
    updateCurrentTime() {
        const timeEl = document.getElementById('current-time');
        const now = new Date();
        timeEl.textContent = now.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit',
            second: '2-digit',
            hour12: true 
        });
    },
    
    // Navigate to page
    navigateToPage(pageName) {
        // Hide all pages
        document.querySelectorAll('.page').forEach(page => {
            page.classList.remove('active');
        });
        
        // Show selected page
        const page = document.getElementById(`${pageName}-page`);
        if (page) {
            page.classList.add('active');
        }
        
        // Update active nav item
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        
        const activeNav = document.querySelector(`[data-page="${pageName}"]`);
        if (activeNav) {
            activeNav.classList.add('active');
        }
        
        // Update page title
        const titles = {
            'overview': 'System Overview',
            'processes': 'Processes & Resources',
            'network': 'Network Activity',
            'applications': 'Applications & Sessions',
            'filesystem': 'File System & Devices',
            'alerts': 'Alerts & Anomalies'
        };
        
        document.getElementById('page-title').textContent = titles[pageName] || 'Dashboard';
    },
    
    // Create a simple chart using canvas
    createLineChart(canvasId, data, label) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        
        // Clear canvas
        ctx.fillStyle = '#1e293b';
        ctx.fillRect(0, 0, width, height);
        
        if (!data || data.length === 0) return;
        
        // Find min and max values
        const values = data.map(d => d.value);
        const minValue = Math.min(...values);
        const maxValue = Math.max(...values);
        const range = maxValue - minValue || 1;
        
        // Draw grid
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 5; i++) {
            const y = (height / 5) * i;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();
        }
        
        // Draw line
        ctx.strokeStyle = '#2563eb';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        data.forEach((point, index) => {
            const x = (width / (data.length - 1)) * index;
            const y = height - ((point.value - minValue) / range) * (height - 20) - 10;
            
            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        
        ctx.stroke();
        
        // Draw points
        ctx.fillStyle = '#2563eb';
        data.forEach((point, index) => {
            const x = (width / (data.length - 1)) * index;
            const y = height - ((point.value - minValue) / range) * (height - 20) - 10;
            
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, Math.PI * 2);
            ctx.fill();
        });
    }
};

// Update time every second
setInterval(() => UI.updateCurrentTime(), 1000);
UI.updateCurrentTime();
