#!/usr/bin/env python3
"""Circuit breaker and SLA monitoring for signal processing."""

import argparse
import json
import os
from datetime import datetime, timezone


class CircuitBreaker:
    """Prevent retry storms from overloading the system."""

    def __init__(self, agent_dir, agent_name, failure_threshold=5, recovery_timeout_sec=300):
        self.agent_dir = agent_dir
        self.agent_name = agent_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.state_file = os.path.join(agent_dir, "shared_intel/signal_bus/circuit_breaker.json")

    def get_state(self):
        """Read current circuit breaker state."""
        try:
            return json.load(open(self.state_file))
        except (FileNotFoundError, json.JSONDecodeError):
            return {"state": "CLOSED", "failure_count": 0, "last_failure_utc": None, "tripped_utc": None}

    def record_failure(self, signal_id, reason):
        """Record a failure. May trip the breaker."""
        state = self.get_state()
        state["failure_count"] = state.get("failure_count", 0) + 1
        state["last_failure_utc"] = datetime.now(timezone.utc).isoformat()
        state["last_signal_id"] = signal_id
        state["last_reason"] = reason
        if state["failure_count"] >= self.failure_threshold:
            state["state"] = "OPEN"
            state["tripped_utc"] = datetime.now(timezone.utc).isoformat()
        self._save(state)
        return state

    def record_success(self):
        """Record a success. May close the breaker."""
        state = self.get_state()
        if state["state"] == "HALF_OPEN":
            state["state"] = "CLOSED"
            state["failure_count"] = 0
        elif state["state"] == "CLOSED":
            state["failure_count"] = max(0, state.get("failure_count", 0) - 1)
        self._save(state)
        return state

    def can_proceed(self):
        """Check if processing is allowed."""
        state = self.get_state()
        if state["state"] == "CLOSED":
            return True
        if state["state"] == "OPEN":
            tripped = datetime.fromisoformat(state["tripped_utc"])
            elapsed = (datetime.now(timezone.utc) - tripped).total_seconds()
            if elapsed >= self.recovery_timeout_sec:
                state["state"] = "HALF_OPEN"
                self._save(state)
                return True
            return False
        if state["state"] == "HALF_OPEN":
            return True  # Allow one test request
        return False

    def reset(self):
        """Force reset the circuit breaker."""
        state = {"state": "CLOSED", "failure_count": 0, "reset_utc": datetime.now(timezone.utc).isoformat()}
        self._save(state)
        return state

    def _save(self, state):
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)


class SLAMonitor:
    """Monitor SLA compliance for signal processing."""

    def __init__(self, agent_dir, agent_name, target_processing_sec=60, target_completion_pct=95):
        self.agent_dir = agent_dir
        self.agent_name = agent_name
        self.target_processing_sec = target_processing_sec
        self.target_completion_pct = target_completion_pct
        self.sla_file = os.path.join(agent_dir, "shared_intel/signal_bus/sla_metrics.jsonl")

    def record_processing_time(self, signal_id, duration_sec, success=True):
        """Record signal processing time."""
        entry = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "signal_id": signal_id,
            "duration_sec": duration_sec,
            "success": success,
            "within_sla": duration_sec <= self.target_processing_sec
        }
        with open(self.sla_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def get_sla_report(self, window_minutes=60):
        """Generate SLA compliance report."""
        cutoff = datetime.now(timezone.utc).timestamp() - (window_minutes * 60)
        entries = []

        try:
            with open(self.sla_file, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        ts = datetime.fromisoformat(entry["timestamp_utc"]).timestamp()
                        if ts >= cutoff:
                            entries.append(entry)
                    except (json.JSONDecodeError, KeyError):
                        continue
        except FileNotFoundError:
            pass

        if not entries:
            return {
                "window_minutes": window_minutes,
                "total_signals": 0,
                "completed": 0,
                "failed": 0,
                "completion_pct": 100.0,
                "avg_time_sec": 0,
                "p95_time_sec": 0,
                "sla_met": True
            }

        completed = sum(1 for e in entries if e.get("success", False))
        failed = len(entries) - completed
        completion_pct = (completed / len(entries)) * 100 if entries else 0

        durations = [e["duration_sec"] for e in entries if "duration_sec" in e]
        avg_time = sum(durations) / len(durations) if durations else 0

        sorted_durations = sorted(durations)
        p95_idx = int(len(sorted_durations) * 0.95)
        p95_time = sorted_durations[p95_idx] if sorted_durations else 0

        sla_met = completion_pct >= self.target_completion_pct and avg_time <= self.target_processing_sec

        return {
            "window_minutes": window_minutes,
            "total_signals": len(entries),
            "completed": completed,
            "failed": failed,
            "completion_pct": round(completion_pct, 2),
            "avg_time_sec": round(avg_time, 2),
            "p95_time_sec": round(p95_time, 2),
            "sla_met": sla_met
        }

    def check_violations(self, window_minutes=30):
        """Check for SLA violations."""
        violations = []
        cutoff = datetime.now(timezone.utc).timestamp() - (window_minutes * 60)

        try:
            with open(self.sla_file, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        ts = datetime.fromisoformat(entry["timestamp_utc"]).timestamp()
                        if ts >= cutoff:
                            if not entry.get("success", False):
                                violations.append({
                                    "signal_id": entry.get("signal_id"),
                                    "type": "failed",
                                    "timestamp": entry.get("timestamp_utc")
                                })
                            elif entry.get("duration_sec", 0) > (2 * self.target_processing_sec):
                                violations.append({
                                    "signal_id": entry.get("signal_id"),
                                    "type": "slow_processing",
                                    "duration_sec": entry.get("duration_sec"),
                                    "timestamp": entry.get("timestamp_utc")
                                })
                    except (json.JSONDecodeError, KeyError):
                        continue
        except FileNotFoundError:
            pass

        # Check completion rate
        report = self.get_sla_report(window_minutes)
        if report["total_signals"] > 0 and report["completion_pct"] < self.target_completion_pct:
            violations.append({
                "type": "low_completion_rate",
                "completion_pct": report["completion_pct"],
                "target_pct": self.target_completion_pct
            })

        return violations

    def get_stuck_signals(self):
        """Find signals that have been processing too long."""
        stuck = []
        in_flight_file = os.path.join(self.agent_dir, "shared_intel/signal_bus/in_flight.json")

        try:
            with open(in_flight_file, 'r') as f:
                in_flight = json.load(f)
                now = datetime.now(timezone.utc)
                for signal_id, started_at in in_flight.items():
                    try:
                        start_time = datetime.fromisoformat(started_at)
                        age = (now - start_time).total_seconds()
                        if age > self.target_processing_sec:
                            stuck.append({
                                "signal_id": signal_id,
                                "age_sec": round(age, 2),
                                "started_at": started_at
                            })
                    except (ValueError, TypeError):
                        continue
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        return stuck


def generate_skill_docs():
    """Generate markdown documentation for all skills."""
    docs = []
    docs.append("# Circuit Breaker and SLA Monitoring\n")
    docs.append("## Circuit Breaker States\n")
    docs.append("- **CLOSED**: Normal operation, processing allowed")
    docs.append("- **OPEN**: Circuit tripped, processing blocked")
    docs.append("- **HALF_OPEN**: Testing recovery, one request allowed\n")
    docs.append("## CLI Usage\n")
    docs.append("```bash")
    docs.append("# Check circuit breaker state")
    docs.append("python3 circuit_breaker.py state --agent-dir /path/to/agent")
    docs.append("")
    docs.append("# Reset circuit breaker")
    docs.append("python3 circuit_breaker.py reset --agent-dir /path/to/agent")
    docs.append("")
    docs.append("# SLA compliance report")
    docs.append("python3 circuit_breaker.py sla --agent-dir /path/to/agent --agent-name nami --window 60")
    docs.append("")
    docs.append("# Check SLA violations")
    docs.append("python3 circuit_breaker.py violations --agent-dir /path/to/agent --agent-name nami")
    docs.append("")
    docs.append("# Find stuck signals")
    docs.append("python3 circuit_breaker.py stuck --agent-dir /path/to/agent --agent-name nami")
    docs.append("```")
    return "\n".join(docs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Circuit breaker and SLA monitoring")
    sub = parser.add_subparsers(dest="command")

    state = sub.add_parser("state", help="Circuit breaker state")
    state.add_argument("--agent-dir", required=True)

    reset = sub.add_parser("reset", help="Reset circuit breaker")
    reset.add_argument("--agent-dir", required=True)

    sla = sub.add_parser("sla", help="SLA report")
    sla.add_argument("--agent-dir", required=True)
    sla.add_argument("--agent-name", required=True)
    sla.add_argument("--window", type=int, default=60)

    violations = sub.add_parser("violations", help="Check SLA violations")
    violations.add_argument("--agent-dir", required=True)
    violations.add_argument("--agent-name", required=True)

    stuck = sub.add_parser("stuck", help="Find stuck signals")
    stuck.add_argument("--agent-dir", required=True)
    stuck.add_argument("--agent-name", required=True)

    docs = sub.add_parser("docs", help="Show documentation")

    args = parser.parse_args()

    if args.command == "state":
        cb = CircuitBreaker(args.agent_dir, "default")
        print(json.dumps(cb.get_state(), indent=2))

    elif args.command == "reset":
        cb = CircuitBreaker(args.agent_dir, "default")
        print(json.dumps(cb.reset(), indent=2))

    elif args.command == "sla":
        monitor = SLAMonitor(args.agent_dir, args.agent_name)
        print(json.dumps(monitor.get_sla_report(args.window), indent=2))

    elif args.command == "violations":
        monitor = SLAMonitor(args.agent_dir, args.agent_name)
        violations = monitor.check_violations()
        if violations:
            print(json.dumps(violations, indent=2))
        else:
            print("No SLA violations detected.")

    elif args.command == "stuck":
        monitor = SLAMonitor(args.agent_dir, args.agent_name)
        stuck = monitor.get_stuck_signals()
        if stuck:
            print(json.dumps(stuck, indent=2))
        else:
            print("No stuck signals.")

    elif args.command == "docs":
        print(generate_skill_docs())

    else:
        parser.print_help()
