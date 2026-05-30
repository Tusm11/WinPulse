"""
LangGraph Orchestrator
- Reads events from Redis Streams
- Runs anomaly detection on each event
- Correlates anomalies across multiple agents
- Generates AI explanations via Groq API
"""

import redis
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, TypedDict
from collections import defaultdict
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from agents.anomaly_scorer import AnomalyScorer
from agents.prophet_models import ProphetModels
from agents.baseline import BehavioralBaseline

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the state that flows through the graph using TypedDict for LangGraph
class OrchestratorState(TypedDict):
    events: List[Dict[str, Any]]              # Raw events from Redis
    anomalies: List[Dict[str, Any]]           # Detected anomalies
    correlated_anomalies: List[Dict[str, Any]] # Grouped anomalies
    explanations: List[Dict[str, Any]]        # AI-generated explanations

class Orchestrator:
    def __init__(self, redis_host=None, redis_port=None, groq_api_key=None):
        """
        Initialize the orchestrator.
        
        Args:
            redis_host: Redis server hostname (defaults to env var)
            redis_port: Redis server port (defaults to env var)
            groq_api_key: Groq API key (defaults to env var)
        """
        # Use provided values or fall back to environment variables
        redis_host = redis_host or os.getenv("REDIS_HOST", "localhost")
        redis_port = int(redis_port or os.getenv("REDIS_PORT", 6379))
        groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        
        # Initialize Groq client only if API key is provided
        if groq_api_key:
            self.groq_client = ChatGroq(api_key=groq_api_key, model_name="llama-3.1-70b-versatile")
            self.use_groq = True
            logger.info("Groq API enabled for explanations")
        else:
            self.groq_client = None
            self.use_groq = False
            logger.info("Groq API disabled - explanations will be skipped")
        
        # Initialize anomaly scoring components
        self.prophet_models = ProphetModels()
        self.baseline = BehavioralBaseline()
        self.anomaly_scorer = AnomalyScorer(self.prophet_models, self.baseline)
        
        # Stream names for each agent
        self.streams = {
            "process_resource": "process_resource_events",
            "network": "network_events",
            "session": "session_events",
            "application": "application_events",
            "filesystem": "filesystem_events",
            "device": "device_events",
            "system_events": "system_events"
        }
        
        # Track last read position for each stream (for resuming)
        self.last_ids = {stream: "0" for stream in self.streams.values()}
        
        # Build LangGraph
        self.graph = self._build_graph()
    
    # Step 1: Consume events from Redis Streams
    def consume_events(self, state: OrchestratorState) -> OrchestratorState:
        """
        Read new events from all Redis Lists.
        
        Uses LPOP to get events from the lists.
        """
        logger.info("Step 1: Consuming events from Redis Lists")
        
        events = []
        
        try:
            # Read from all lists
            for stream_name in self.last_ids.keys():
                # LPOP: read events from the list (FIFO)
                # Read up to 100 events
                for _ in range(100):
                    event_json = self.redis_client.lpop(stream_name)
                    if not event_json:
                        break
                    
                    try:
                        event = json.loads(event_json)
                        events.append(event)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse event: {event_json}")
            
            state["events"] = events
            logger.info(f"Consumed {len(events)} events")
        
        except Exception as e:
            logger.error(f"Error consuming events: {e}")
        
        return state
    
    # Step 2: Detect anomalies in each event
    def detect_anomalies(self, state: OrchestratorState) -> OrchestratorState:
        """
        Run anomaly scoring on each event using AnomalyScorer.
        
        Filters out normal events, keeps only anomalies.
        """
        logger.info("Step 2: Detecting anomalies")
        
        anomalies = []
        
        for event in state["events"]:
            try:
                metric = event.get("metric")
                value = float(event.get("value", 0))
                metadata = json.loads(event.get("metadata", "{}")) if isinstance(event.get("metadata"), str) else event.get("metadata", {})
                
                # Use AnomalyScorer to create detailed report
                report = self.anomaly_scorer.create_anomaly_report(metric, value, metadata)
                
                # Only keep anomalies (is_anomaly = True)
                if report["is_anomaly"]:
                    report["timestamp"] = event.get("timestamp")
                    report["agent"] = event.get("agent")
                    anomalies.append(report)
            
            except Exception as e:
                logger.error(f"Error scoring event: {e}")
        
        state["anomalies"] = anomalies
        logger.info(f"Detected {len(anomalies)} anomalies")
        
        return state
    
    # Step 3: Correlate anomalies across agents
    def correlate_anomalies(self, state: OrchestratorState) -> OrchestratorState:
        """
        Group related anomalies that occurred within same time window.
        
        Example: High CPU + High Network + New Process = coordinated attack
        """
        logger.info("Step 3: Correlating anomalies")
        
        if not state["anomalies"]:
            state["correlated_anomalies"] = []
            return state
        
        # Group anomalies by time window (5-minute windows)
        time_windows = defaultdict(list)
        
        for anomaly in state["anomalies"]:
            timestamp = datetime.fromisoformat(anomaly["timestamp"])
            # Round to nearest 5-minute window
            window = timestamp.replace(minute=(timestamp.minute // 5) * 5, second=0, microsecond=0)
            time_windows[window].append(anomaly)
        
        # Create correlated anomaly groups
        correlated = []
        
        for window, anomalies_in_window in time_windows.items():
            if len(anomalies_in_window) > 1:
                # Multiple anomalies in same window = correlated
                agents_involved = set(a["agent"] for a in anomalies_in_window)
                
                correlation = {
                    "timestamp": window.isoformat(),
                    "anomaly_count": len(anomalies_in_window),
                    "agents_involved": list(agents_involved),
                    "anomalies": anomalies_in_window,
                    "correlation_score": len(agents_involved) / len(self.streams)  # % of agents involved
                }
                correlated.append(correlation)
        
        state["correlated_anomalies"] = correlated
        logger.info(f"Found {len(correlated)} correlated anomaly groups")
        
        return state
    
    # Step 4: Generate AI explanations
    def generate_explanations(self, state: OrchestratorState) -> OrchestratorState:
        """
        Call Groq API to generate plain English explanations for anomalies.
        Skipped if Groq API key is not configured.
        """
        logger.info("Step 4: Generating AI explanations")
        
        explanations = []
        
        # Skip if Groq is not enabled
        if not self.use_groq:
            logger.info("Groq API not configured - skipping explanations")
            state["explanations"] = []
            return state
        
        for correlation in state["correlated_anomalies"]:
            try:
                # Build prompt for Groq
                anomaly_summary = "\n".join([
                    f"- {a['agent']}: {a['metric']} = {a['actual_value']} (z-score: {a['z_score']})"
                    for a in correlation["anomalies"]
                ])
                
                prompt = f"""
                A Windows security system detected the following anomalies at {correlation['timestamp']}:
                
                {anomaly_summary}
                
                These anomalies occurred within the same 5-minute window across {len(correlation['agents_involved'])} different monitoring agents.
                
                Provide a brief (2-3 sentences) plain English explanation of what might be happening and why it's suspicious.
                Focus on security implications, not technical details.
                """
                
                # Call Groq API
                response = self.groq_client.invoke(prompt)
                explanation_text = response.content
                
                explanation = {
                    "timestamp": correlation["timestamp"],
                    "anomaly_count": correlation["anomaly_count"],
                    "agents_involved": correlation["agents_involved"],
                    "explanation": explanation_text,
                    "correlation_score": correlation["correlation_score"]
                }
                explanations.append(explanation)
                
                logger.info(f"Generated explanation for {len(correlation['anomalies'])} anomalies")
            
            except Exception as e:
                logger.error(f"Error generating explanation: {e}")
        
        state["explanations"] = explanations
        return state
    
    # Build the LangGraph state machine
    def _build_graph(self):
        """
        Construct the LangGraph workflow.
        
        Flow: Consume -> Detect -> Correlate -> Explain -> END
        """
        graph = StateGraph(OrchestratorState)
        
        # Add nodes (steps)
        graph.add_node("consume", self.consume_events)
        graph.add_node("detect", self.detect_anomalies)
        graph.add_node("correlate", self.correlate_anomalies)
        graph.add_node("explain", self.generate_explanations)
        
        # Add edges (flow)
        graph.add_edge("consume", "detect")
        graph.add_edge("detect", "correlate")
        graph.add_edge("correlate", "explain")
        graph.add_edge("explain", END)
        
        # Set entry point
        graph.set_entry_point("consume")
        
        return graph.compile()
    
    # Run the orchestrator
    def run(self):
        """
        Main loop: continuously run the orchestration workflow.
        """
        logger.info("Orchestrator started")
        
        try:
            while True:
                # Create initial state
                state: OrchestratorState = {
                    "events": [],
                    "anomalies": [],
                    "correlated_anomalies": [],
                    "explanations": []
                }
                
                # Run the graph
                final_state = self.graph.invoke(state)
                
                # Store results in database (you'll implement this)
                if final_state["explanations"]:
                    self._store_results(final_state["explanations"])
                
                # Sleep before next cycle
                import time
                time.sleep(5)
        
        except KeyboardInterrupt:
            logger.info("Orchestrator stopped")
    
    # Store results in database
    def _store_results(self, explanations: List[Dict]):
        """
        Store anomaly explanations in PostgreSQL.
        
        Args:
            explanations: List of explanation dictionaries
        """
        try:
            for exp in explanations:
                # Insert into database
                # query = "INSERT INTO anomalies (timestamp, agents, explanation) VALUES (%s, %s, %s)"
                # db.execute(query, (exp["timestamp"], json.dumps(exp["agents_involved"]), exp["explanation"]))
                logger.info(f"Stored explanation: {exp['explanation'][:50]}...")
        except Exception as e:
            logger.error(f"Error storing results: {e}")

if __name__ == "__main__":
    orchestrator = Orchestrator()
    orchestrator.run()