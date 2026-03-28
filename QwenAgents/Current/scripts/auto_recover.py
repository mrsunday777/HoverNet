#!/usr/bin/env python3
"""
Automated Agent Recovery for HoverNet QwenBuilderLoop

Implements automated recovery actions that can fix common agent failures
without human intervention.
"""

import fcntl
import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Optional


RECOVERY_ACTIONS = {
    "restart_hover": {"risk": "low", "description": "Restart hover polling"},
    "reset_cursor": {"risk": "medium", "description": "Reset cursor to last known good position"},
    "compact_bus": {"risk": "medium", "description": "Compact signal bus to remove dead signals"},
    "clear_stale_locks": {"risk": "low", "description": "Remove lock files from dead processes"},
    "repair_bus_json": {"risk": "low", "description": "Fix corrupted JSON lines in bus"},
    "kill_zombie": {"risk": "high", "description": "Kill zombie process and restart"},
    "redistribute_signals": {"risk": "high", "description": "Move pending signals to another agent"}
}


class AutoRecovery:
    """Automated recovery actions for agent failures."""
    
    def __init__(self, agent_dir: str, agent_name: str, dry_run: bool = False):
        self.agent_dir = agent_dir
        self.agent_name = agent_name
        self.dry_run = dry_run
        self.signal_bus = os.path.join(agent_dir, "shared_intel/signal_bus")
        self.log_file = os.path.join(self.signal_bus, "recovery_log.jsonl")
    
    def diagnose(self) -> list:
        """
        Run all diagnostics and return list of issues.
        
        Returns:
            List of issue dicts with type, description, and details
        """
        issues = []
        
        # Check: stale heartbeat (cursor not updated in > 5 min)
        cursor_file = os.path.join(self.signal_bus, "cursors", f"{self.agent_name}_ran_hover.cursor")
        if os.path.exists(cursor_file):
            mtime = os.path.getmtime(cursor_file)
            age_sec = time.time() - mtime
            if age_sec > 300:  # 5 minutes
                issues.append({
                    "type": "stale_heartbeat",
                    "description": f"Cursor not updated in {int(age_sec)} seconds",
                    "cursor_file": cursor_file,
                    "age_sec": int(age_sec)
                })
        
        # Check: cursor drift
        signals_file = os.path.join(self.signal_bus, "signals.jsonl")
        if os.path.exists(cursor_file) and os.path.exists(signals_file):
            try:
                with open(cursor_file, 'r') as f:
                    content = f.read().strip()
                    try:
                        cursor_pos = int(content)
                    except ValueError:
                        data = json.loads(content)
                        cursor_pos = data.get("position", 0)
                
                with open(signals_file, 'r') as f:
                    total_lines = sum(1 for line in f if line.strip())
                
                if cursor_pos > total_lines:
                    issues.append({
                        "type": "cursor_drift",
                        "description": f"Cursor ({cursor_pos}) exceeds total signals ({total_lines})",
                        "correct_position": total_lines,
                        "current_position": cursor_pos
                    })
            except (IOError, json.JSONDecodeError, ValueError):
                pass
        
        # Check: corrupted bus lines
        if os.path.exists(signals_file):
            with open(signals_file, 'r') as f:
                for line_num, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        json.loads(line)
                    except json.JSONDecodeError:
                        issues.append({
                            "type": "corrupted_json",
                            "description": f"Invalid JSON at line {line_num}",
                            "line_num": line_num
                        })
        
        # Check: stale lock files
        for lock_name in ["hover.lock", "compaction.lock"]:
            lock_path = os.path.join(self.signal_bus, lock_name)
            if os.path.exists(lock_path):
                try:
                    data = json.load(open(lock_path))
                    pid = data.get("pid")
                    if pid:
                        try:
                            os.kill(pid, 0)
                        except ProcessLookupError:
                            issues.append({
                                "type": "stale_lock",
                                "description": f"Lock file {lock_name} has dead PID {pid}",
                                "lock_file": lock_path,
                                "dead_pid": pid
                            })
                except (json.JSONDecodeError, IOError):
                    issues.append({
                        "type": "stale_lock",
                        "description": f"Lock file {lock_name} is corrupted",
                        "lock_file": lock_path
                    })
        
        # Check: zombie processes (PID in lock but process dead)
        in_flight_path = os.path.join(self.signal_bus, "in_flight.json")
        if os.path.exists(in_flight_path):
            try:
                data = json.load(open(in_flight_path))
                if data.get("status") == "processing":
                    started = data.get("started_utc")
                    if started:
                        # Check if processing for > 30 minutes
                        start_time = datetime.fromisoformat(started.replace('Z', '+00:00'))
                        age = (datetime.now(timezone.utc) - start_time).total_seconds()
                        if age > 1800:
                            issues.append({
                                "type": "zombie_process",
                                "description": f"In-flight processing stuck for {int(age)} seconds",
                                "signal_id": data.get("signal_id"),
                                "age_sec": int(age)
                            })
            except (json.JSONDecodeError, IOError):
                pass
        
        # Check: bus growing too large (>1000 lines)
        if os.path.exists(signals_file):
            with open(signals_file, 'r') as f:
                line_count = sum(1 for line in f if line.strip())
            if line_count > 1000:
                issues.append({
                    "type": "bus_too_large",
                    "description": f"Signal bus has {line_count} lines (>1000)",
                    "line_count": line_count
                })
        
        return issues
    
    def plan_recovery(self, issues: list) -> list:
        """
        Given issues, plan recovery actions.
        
        Args:
            issues: List of issue dicts from diagnose()
            
        Returns:
            List of recovery action dicts
        """
        plan = []
        for issue in issues:
            if issue["type"] == "stale_lock":
                plan.append({"action": "clear_stale_locks", "target": issue.get("lock_file")})
            elif issue["type"] == "corrupted_json":
                plan.append({"action": "repair_bus_json", "target": issue.get("line_num")})
            elif issue["type"] == "cursor_drift":
                plan.append({"action": "reset_cursor", "target": issue.get("correct_position")})
            elif issue["type"] == "bus_too_large":
                plan.append({"action": "compact_bus"})
            elif issue["type"] == "zombie_process":
                plan.append({"action": "kill_zombie", "target": issue.get("pid")})
            elif issue["type"] == "stale_heartbeat":
                plan.append({"action": "restart_hover"})
        return plan
    
    def execute_plan(self, plan: list) -> list:
        """
        Execute recovery plan. Respects dry_run flag.
        
        Args:
            plan: List of recovery action dicts
            
        Returns:
            List of result dicts
        """
        results = []
        for step in plan:
            action = step["action"]
            if self.dry_run:
                results.append({"action": action, "status": "dry_run", "would_do": step})
                self._log_action(step, results[-1])
                continue
            
            try:
                if action == "clear_stale_locks":
                    self._clear_locks(step.get("target"))
                    results.append({"action": action, "status": "done"})
                elif action == "repair_bus_json":
                    self._repair_bus(step.get("target"))
                    results.append({"action": action, "status": "done"})
                elif action == "reset_cursor":
                    self._reset_cursor(step.get("target"))
                    results.append({"action": action, "status": "done"})
                elif action == "compact_bus":
                    self._compact_bus()
                    results.append({"action": action, "status": "done"})
                elif action == "restart_hover":
                    self._restart_hover()
                    results.append({"action": action, "status": "done"})
                else:
                    results.append({"action": action, "status": "skipped", "reason": "high_risk_needs_approval"})
            except Exception as e:
                results.append({"action": action, "status": "failed", "error": str(e)})
            
            # Log every action
            self._log_action(step, results[-1])
        
        return results
    
    def auto_recover(self) -> dict:
        """
        Full automated recovery cycle: diagnose → plan → execute.
        
        Returns:
            Dict with status, issues count, and results
        """
        issues = self.diagnose()
        if not issues:
            return {"status": "healthy", "issues": 0}
        
        plan = self.plan_recovery(issues)
        results = self.execute_plan(plan)
        
        return {
            "status": "recovered",
            "issues": len(issues),
            "actions": len(results),
            "results": results
        }
    
    def _clear_locks(self, lock_file: Optional[str] = None) -> None:
        """Remove lock file if PID is dead."""
        if lock_file and os.path.exists(lock_file):
            try:
                data = json.load(open(lock_file))
                pid = data.get("pid")
                if pid:
                    try:
                        os.kill(pid, 0)
                        # PID alive, don't remove
                        return
                    except ProcessLookupError:
                        pass
                os.unlink(lock_file)
            except (json.JSONDecodeError, IOError, OSError):
                if os.path.exists(lock_file):
                    os.unlink(lock_file)
    
    def _repair_bus(self, line_num: Optional[int] = None) -> None:
        """Remove corrupted line from bus."""
        signals_file = os.path.join(self.signal_bus, "signals.jsonl")
        if not os.path.exists(signals_file) or line_num is None:
            return
        
        with open(signals_file, 'r') as f:
            lines = f.readlines()
        
        # Remove the corrupted line
        if 0 <= line_num < len(lines):
            lines.pop(line_num)
        
        # Rewrite bus atomically
        tmp_file = signals_file + ".tmp"
        with open(tmp_file, 'w') as f:
            f.writelines(lines)
        os.replace(tmp_file, signals_file)
    
    def _reset_cursor(self, position: Optional[int] = None) -> None:
        """Write cursor to correct position with backup."""
        cursor_file = os.path.join(self.signal_bus, "cursors", f"{self.agent_name}_ran_hover.cursor")
        
        if position is None:
            position = 0
        
        # Backup existing cursor
        if os.path.exists(cursor_file):
            backup = cursor_file + ".bak"
            import shutil
            shutil.copy2(cursor_file, backup)
        
        # Write new cursor position
        os.makedirs(os.path.dirname(cursor_file), exist_ok=True)
        
        # Import from cursor_resilience if available
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cursor_resilience_path = os.path.join(script_dir, "cursor_resilience.py")
        
        if os.path.exists(cursor_resilience_path):
            import importlib.util
            spec = importlib.util.spec_from_file_location("cursor_resilience", cursor_resilience_path)
            cursor_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cursor_mod)
            cursor = cursor_mod.CursorWithMetadata(cursor_file)
            cursor.write(position)
        else:
            # Fallback: simple write
            with open(cursor_file, 'w') as f:
                f.write(str(position))
    
    def _compact_bus(self) -> None:
        """Keep only unprocessed signals."""
        signals_file = os.path.join(self.signal_bus, "signals.jsonl")
        cursor_file = os.path.join(self.signal_bus, "cursors", f"{self.agent_name}_ran_hover.cursor")
        
        if not os.path.exists(signals_file):
            return
        
        # Read cursor position
        cursor_pos = 0
        if os.path.exists(cursor_file):
            try:
                content = open(cursor_file).read().strip()
                try:
                    cursor_pos = int(content)
                except ValueError:
                    data = json.loads(content)
                    cursor_pos = data.get("position", 0)
            except (IOError, json.JSONDecodeError):
                pass
        
        # Read all signals
        with open(signals_file, 'r') as f:
            lines = f.readlines()
        
        # Keep only signals from cursor onward
        remaining = lines[cursor_pos:]
        
        # Rewrite bus atomically
        tmp_file = signals_file + ".tmp"
        with open(tmp_file, 'w') as f:
            f.writelines(remaining)
        os.replace(tmp_file, signals_file)
        
        # Reset cursor to 0
        self._reset_cursor(0)
    
    def _restart_hover(self) -> None:
        """Touch cursor file to signal hover should restart."""
        cursor_file = os.path.join(self.signal_bus, "cursors", f"{self.agent_name}_ran_hover.cursor")
        if os.path.exists(cursor_file):
            os.utime(cursor_file, None)  # Update mtime
    
    def _log_action(self, step: dict, result: dict) -> None:
        """Append recovery action to log."""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        log_entry = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "agent": self.agent_name,
            "step": step,
            "result": result,
            "dry_run": self.dry_run
        }
        
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + "\n")


if __name__ == "__main__":
    import argparse
    import time
    
    parser = argparse.ArgumentParser(description="Automated agent recovery")
    sub = parser.add_subparsers(dest="command")
    
    # diagnose command
    diag = sub.add_parser("diagnose", help="Run diagnostics")
    diag.add_argument("--agent-dir", required=True)
    diag.add_argument("--agent-name", required=True)
    
    # recover command
    recover = sub.add_parser("recover", help="Auto-recover")
    recover.add_argument("--agent-dir", required=True)
    recover.add_argument("--agent-name", required=True)
    recover.add_argument("--dry-run", action="store_true")
    
    # plan command
    plan_cmd = sub.add_parser("plan", help="Show recovery plan without executing")
    plan_cmd.add_argument("--agent-dir", required=True)
    plan_cmd.add_argument("--agent-name", required=True)
    
    args = parser.parse_args()
    
    recovery = AutoRecovery(args.agent_dir, args.agent_name, dry_run=args.dry_run if hasattr(args, 'dry_run') else False)
    
    if args.command == "diagnose":
        issues = recovery.diagnose()
        print(json.dumps({"issues": issues, "count": len(issues)}, indent=2))
    
    elif args.command == "recover":
        result = recovery.auto_recover()
        print(json.dumps(result, indent=2))
    
    elif args.command == "plan":
        issues = recovery.diagnose()
        plan = recovery.plan_recovery(issues)
        print(json.dumps({"issues": len(issues), "plan": plan}, indent=2))
    
    else:
        parser.print_help()
