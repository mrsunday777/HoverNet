#!/usr/bin/env python3
"""Self-healing loop for signal bus — autonomous recovery daemon."""

import sys
import os
import time
import json
import glob
from datetime import datetime, timezone

# Import sibling modules
# bus_health and dead_letter resolve from same directory
from bus_health import validate_json_lines, validate_cursor_drift, repair_bus, scan_orphan_signals, compact_bus_verified, log_self_healing_event
from dead_letter import move_to_dead_letter, expire_old_signals, detect_poison_pill, audit_log, list_dead_letters


class SelfHealLoop:
    """Autonomous recovery daemon for signal bus health."""
    
    def __init__(self, agent_dir, dry_run=False, verbose=False):
        self.agent_dir = agent_dir
        self.dry_run = dry_run
        self.verbose = verbose
        self.signals_file = os.path.join(agent_dir, "shared_intel/signal_bus/signals.jsonl")
        self.cursor_file = None  # auto-detect from cursors dir
        self.completions_dir = os.path.join(agent_dir, "shared_intel/signal_bus/completions")
        self.stats = {"checks": 0, "heals": 0, "errors": 0, "skipped": 0}
    
    def detect_cursor_file(self):
        """
        Scan cursors dir for *_ran_hover.cursor files.
        Return the first one found (or fall back to *_hover.cursor).
        """
        cursors_dir = os.path.join(self.agent_dir, "shared_intel/signal_bus/cursors")
        
        if not os.path.isdir(cursors_dir):
            return None
        
        # Look for *_ran_hover.cursor first
        for filename in os.listdir(cursors_dir):
            if filename.endswith('_ran_hover.cursor'):
                self.cursor_file = os.path.join(cursors_dir, filename)
                return self.cursor_file
        
        # Fall back to *_hover.cursor
        for filename in os.listdir(cursors_dir):
            if filename.endswith('_hover.cursor'):
                self.cursor_file = os.path.join(cursors_dir, filename)
                return self.cursor_file
        
        return None
    
    def run_diagnostics(self):
        """
        Run ALL checks in sequence, return a health report.
        """
        report = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "agent_dir": self.agent_dir,
            "checks": [],
            "issues_found": 0,
            "issues_healed": 0
        }
        
        # Check 1: JSON validity
        bad_lines = validate_json_lines(self.signals_file)
        if bad_lines:
            report["checks"].append({"check": "json_validity", "status": "FAIL", "bad_lines": len(bad_lines)})
            report["issues_found"] += 1
        else:
            report["checks"].append({"check": "json_validity", "status": "PASS"})
        
        # Check 2: Cursor drift
        if self.cursor_file:
            drift = validate_cursor_drift(self.cursor_file, self.signals_file)
            if drift["drifted"]:
                report["checks"].append({"check": "cursor_drift", "status": "FAIL", "gap": drift["gap"]})
                report["issues_found"] += 1
            else:
                report["checks"].append({"check": "cursor_drift", "status": "PASS"})
        
        # Check 3: Orphan signals (signals with no completion after 30 min)
        orphans = scan_orphan_signals(self.signals_file, self.completions_dir)
        if orphans:
            report["checks"].append({"check": "orphan_signals", "status": "WARN", "count": len(orphans)})
        
        # Check 4: Bus size (backpressure check)
        total_lines = 0
        if os.path.exists(self.signals_file):
            with open(self.signals_file, 'r') as f:
                total_lines = sum(1 for line in f if line.strip())
        if total_lines > 500:
            report["checks"].append({"check": "bus_size", "status": "WARN", "lines": total_lines})
        
        # Check 5: Poison pill detection
        dead_letter_file = os.path.join(self.agent_dir, "shared_intel/signal_bus/dead_letter.jsonl")
        if os.path.exists(dead_letter_file):
            poison_count = 0
            with open(dead_letter_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        signal_id = data.get('signal_id', '')
                        poison_result = detect_poison_pill(self.agent_dir, signal_id, max_retries=3)
                        if poison_result["is_poison"]:
                            poison_count += 1
                    except json.JSONDecodeError:
                        continue
            
            if poison_count > 0:
                report["checks"].append({"check": "poison_pills", "status": "WARN", "count": poison_count})
        
        return report
    
    def auto_heal(self, report):
        """
        Fix what diagnostics found.
        """
        healed = []
        
        for check in report["checks"]:
            if check["status"] == "PASS":
                continue
            
            if check["check"] == "json_validity" and not self.dry_run:
                result = repair_bus(self.signals_file)
                healed.append({"action": "repair_bus", "result": result})
                log_self_healing_event(self.agent_dir, "bus_repaired", str(result))
            
            elif check["check"] == "cursor_drift" and not self.dry_run:
                # Reset cursor to actual line count
                total = 0
                if os.path.exists(self.signals_file):
                    with open(self.signals_file, 'r') as f:
                        total = sum(1 for line in f if line.strip())
                if self.cursor_file:
                    with open(self.cursor_file, 'w') as f:
                        f.write(str(total))
                healed.append({"action": "cursor_reset", "new_value": total})
                log_self_healing_event(self.agent_dir, "cursor_drift_detected", f"reset to {total}")
            
            elif check["check"] == "bus_size" and not self.dry_run:
                archive_dir = os.path.join(self.agent_dir, "shared_intel/signal_bus/archive")
                result = compact_bus_verified(self.signals_file, archive_dir)
                healed.append({"action": "compaction", "result": result})
                log_self_healing_event(self.agent_dir, "compaction_done", str(result))
        
        report["issues_healed"] = len(healed)
        report["heals"] = healed
        return report
    
    def run_once(self):
        """Single pass of diagnostics and healing."""
        self.detect_cursor_file()
        report = self.run_diagnostics()
        if report["issues_found"] > 0:
            report = self.auto_heal(report)
        self.stats["checks"] += 1
        self.stats["heals"] += report["issues_healed"]
        return report
    
    def run_continuous(self, interval_sec=60):
        """Run as daemon mode."""
        print(f"Self-heal loop starting for {self.agent_dir} (interval: {interval_sec}s, dry_run: {self.dry_run})")
        try:
            while True:
                report = self.run_once()
                if self.verbose or report["issues_found"] > 0:
                    print(json.dumps(report, indent=2))
                time.sleep(interval_sec)
        except KeyboardInterrupt:
            print(f"\nStopped. Stats: {json.dumps(self.stats)}")


def run_fleet(fleet_root, dry_run=False, verbose=False):
    """
    Run diagnostics across every agent in the fleet.
    
    Args:
        fleet_root: Root directory containing agent directories
        dry_run: Check only, don't fix
        verbose: Print all results
    
    Returns:
        Dict of agent_name -> health report
    """
    results = {}
    
    for agent_name in sorted(os.listdir(fleet_root)):
        agent_dir = os.path.join(fleet_root, agent_name)
        if not os.path.isdir(agent_dir):
            continue
        
        signals = os.path.join(agent_dir, "shared_intel/signal_bus/signals.jsonl")
        if not os.path.exists(signals):
            continue
        
        loop = SelfHealLoop(agent_dir, dry_run=dry_run, verbose=verbose)
        results[agent_name] = loop.run_once()
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Self-healing loop for signal bus")
    parser.add_argument("--agent-dir", help="Single agent directory")
    parser.add_argument("--fleet-root", help="Scan all agents in fleet root")
    parser.add_argument("--dry-run", action="store_true", help="Check only, don't fix")
    parser.add_argument("--continuous", action="store_true", help="Run as daemon")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between checks")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    
    if args.fleet_root:
        results = run_fleet(args.fleet_root, dry_run=args.dry_run, verbose=args.verbose)
        print(json.dumps(results, indent=2))
    elif args.agent_dir:
        loop = SelfHealLoop(args.agent_dir, dry_run=args.dry_run, verbose=args.verbose)
        if args.continuous:
            loop.run_continuous(args.interval)
        else:
            report = loop.run_once()
            print(json.dumps(report, indent=2))
    else:
        parser.print_help()
