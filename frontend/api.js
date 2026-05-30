/**
 * API Module - Handles all backend communication
 */

const API = {
    BASE_URL: 'http://localhost:8000/api',
    WS_URL: 'ws://localhost:8000/ws',
    USER_ID: 1,
    
    // Initialize WebSocket connection
    initWebSocket() {
        try {
            this.ws = new WebSocket(`${this.WS_URL}/${this.USER_ID}`);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                UI.updateConnectionStatus(true);
                // Send ping every 30 seconds to keep connection alive
                this.pingInterval = setInterval(() => {
                    if (this.ws.readyState === WebSocket.OPEN) {
                        this.ws.send('ping');
                    }
                }, 30000);
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleWebSocketMessage(message);
                } catch (e) {
                    // Handle ping/pong responses
                    if (event.data === 'pong') {
                        console.log('Pong received');
                    }
                }
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                UI.updateConnectionStatus(false);
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                UI.updateConnectionStatus(false);
                clearInterval(this.pingInterval);
                // Attempt to reconnect after 3 seconds
                setTimeout(() => this.initWebSocket(), 3000);
            };
        } catch (error) {
            console.error('Failed to initialize WebSocket:', error);
            UI.updateConnectionStatus(false);
        }
    },
    
    // Handle incoming WebSocket messages
    handleWebSocketMessage(message) {
        if (message.type === 'anomaly') {
            console.log('New anomaly detected:', message.data);
            UI.showToast('New anomaly detected!');
            // Refresh anomalies list
            this.getAnomalies().then(data => {
                UI.updateRecentAnomalies(data);
            });
        } else if (message.type === 'status') {
            console.log('Status update:', message.data);
            UI.updateSystemStatus(message.data);
        }
    },
    
    // GET /api/anomalies
    async getAnomalies(skip = 0, limit = 50, severity = null, hours = 24) {
        try {
            let url = `${this.BASE_URL}/anomalies?skip=${skip}&limit=${limit}&hours=${hours}&user_id=${this.USER_ID}`;
            if (severity) {
                url += `&severity=${severity}`;
            }
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching anomalies:', error);
            return [];
        }
    },
    
    // GET /api/anomalies/stats/summary
    async getAnomalyStats(hours = 24) {
        try {
            const response = await fetch(
                `${this.BASE_URL}/anomalies/stats/summary?hours=${hours}&user_id=${this.USER_ID}`
            );
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching anomaly stats:', error);
            return null;
        }
    },
    
    // GET /api/anomalies/{id}
    async getAnomalyDetail(anomalyId) {
        try {
            const response = await fetch(`${this.BASE_URL}/anomalies/${anomalyId}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching anomaly detail:', error);
            return null;
        }
    },
    
    // GET /api/correlated-anomalies
    async getCorrelatedAnomalies(skip = 0, limit = 50, hours = 24) {
        try {
            const response = await fetch(
                `${this.BASE_URL}/correlated-anomalies?skip=${skip}&limit=${limit}&hours=${hours}&user_id=${this.USER_ID}`
            );
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching correlated anomalies:', error);
            return [];
        }
    },
    
    // GET /api/metrics/timeseries
    async getMetricTimeseries(metric, agent, hours = 24) {
        try {
            const response = await fetch(
                `${this.BASE_URL}/metrics/timeseries?metric=${metric}&agent=${agent}&hours=${hours}&user_id=${this.USER_ID}`
            );
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching metric timeseries:', error);
            return null;
        }
    },
    
    // GET /api/metrics/latest
    async getLatestMetrics() {
        try {
            const response = await fetch(`${this.BASE_URL}/metrics/latest?user_id=${this.USER_ID}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching latest metrics:', error);
            return [];
        }
    },
    
    // GET /api/system/status
    async getSystemStatus() {
        try {
            const response = await fetch(`${this.BASE_URL}/system/status?user_id=${this.USER_ID}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching system status:', error);
            return null;
        }
    },
    
    // GET /api/system/agents
    async getAgentStatus() {
        try {
            const response = await fetch(`${this.BASE_URL}/system/agents?user_id=${this.USER_ID}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching agent status:', error);
            return [];
        }
    },
    
    // GET /api/system/warmup
    async getWarmupProgress() {
        try {
            const response = await fetch(`${this.BASE_URL}/system/warmup?user_id=${this.USER_ID}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching warmup progress:', error);
            return null;
        }
    },
    
    // GET /api/system/overview
    async getDashboardOverview() {
        try {
            const response = await fetch(`${this.BASE_URL}/system/overview?user_id=${this.USER_ID}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching dashboard overview:', error);
            return null;
        }
    }
};

// Initialize WebSocket on page load
document.addEventListener('DOMContentLoaded', () => {
    API.initWebSocket();
});
