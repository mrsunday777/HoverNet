import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path


# F007: Retry fields for signals
RETRY_FIELDS = {
    "retry_count": 0,        # times this signal has been retried
    "max_retries": 3,        # give up after this many
    "first_attempt_utc": None,  # when first consumed
    "last_attempt_utc": None,   # when last retried
    "backoff_until_utc": None,  # don't retry before this time
    "failure_reason": None      # why it failed last time
}


class RetryManager:
    def __init__(self, agent_dir, agent_name=None, max_retries=3, base_backoff_sec=60):
        self.agent_dir = Path(agent_dir)
        self.agent_name = agent_name or self.agent_dir.name
        self.max_retries = max_retries
        self.base_backoff_sec = base_backoff_sec
        self.signals_file = self.agent_dir / "shared_intel" / "signal_bus" / "signals.jsonl"
        self.dead_letter_file = self.agent_dir / "shared_intel" / "signal_bus" / "dead_letter.jsonl"
        self.retry_state_file = self.agent_dir / "shared_intel" / "signal_bus" / "retry_state.json"
        self.cursor_file = self.agent_dir / "shared_intel" / "signal_bus" / "cursors" / f"{self.agent_name}_ran_hover.cursor"
        self.completions_dir = self.agent_dir / "shared_intel" / "signal_bus" / "completions"

    def _load_retry_state(self):
        """Load retry state from JSON file."""
        if self.retry_state_file.exists():
            with open(self.retry_state_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_retry_state(self, state):
        """Save retry state to JSON file."""
        self.retry_state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.retry_state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def _now_utc(self):
        """Get current UTC timestamp."""
        return datetime.now(timezone.utc).isoformat()

    def _parse_utc(self, timestamp_str):
        """Parse UTC timestamp string to datetime."""
        if not timestamp_str:
            return None
        try:
            # Handle various ISO formats
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            return datetime.fromisoformat(timestamp_str)
        except (ValueError, TypeError):
            return None

    def _move_to_dead_letter(self, signal_id, reason):
        """Move a signal to dead letter queue."""
        state = self._load_retry_state()
        signal_data = state.get(signal_id, {})

        dead_letter_entry = {
            "signal_id": signal_id,
            "reason": reason,
            "timestamp_utc": self._now_utc(),
            "retry_count": signal_data.get("retry_count", 0),
            "original_signal": signal_data.get("signal", {})
        }

        self.dead_letter_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.dead_letter_file, 'a') as f:
            f.write(json.dumps(dead_letter_entry) + "\n")

        # Remove from retry state
        if signal_id in state:
            del state[signal_id]
            self._save_retry_state(state)

        return dead_letter_entry

    def mark_failed(self, signal_id, reason):
        """Mark a signal as failed and schedule retry or dead letter."""
        state = self._load_retry_state()

        if signal_id not in state:
            state[signal_id] = {
                "signal_id": signal_id,
                "retry_count": 0,
                "max_retries": self.max_retries,
                "first_attempt_utc": self._now_utc(),
                "last_attempt_utc": None,
                "backoff_until_utc": None,
                "failure_reason": None,
                "signal": {}
            }

        entry = state[signal_id]
        entry["retry_count"] += 1
        entry["last_attempt_utc"] = self._now_utc()
        entry["failure_reason"] = reason

        # Calculate exponential backoff
        backoff_sec = self.base_backoff_sec * (2 ** entry["retry_count"])
        backoff_until = datetime.now(timezone.utc) + timedelta(seconds=backoff_sec)
        entry["backoff_until_utc"] = backoff_until.isoformat()

        # Check if max retries exceeded
        if entry["retry_count"] >= entry["max_retries"]:
            self._move_to_dead_letter(signal_id, reason)
            return {
                "signal_id": signal_id,
                "retry_count": entry["retry_count"],
                "action": "dead_lettered",
                "backoff_sec": backoff_sec
            }

        self._save_retry_state(state)
        return {
            "signal_id": signal_id,
            "retry_count": entry["retry_count"],
            "action": "retry_scheduled",
            "backoff_sec": backoff_sec
        }

    def get_retryable_signals(self):
        """Get signals ready for retry (backoff expired and under max retries)."""
        state = self._load_retry_state()
        now = datetime.now(timezone.utc)
        retryable = []

        for signal_id, entry in state.items():
            retry_count = entry.get("retry_count", 0)
            max_retries = entry.get("max_retries", self.max_retries)
            backoff_until = self._parse_utc(entry.get("backoff_until_utc"))

            # Check if under max retries and backoff expired
            if retry_count < max_retries:
                if backoff_until is None or now > backoff_until:
                    retryable.append({
                        "signal_id": signal_id,
                        "retry_count": retry_count,
                        "signal": entry.get("signal", {})
                    })

        return retryable

    def retry_signal(self, signal_id):
        """Re-append a signal to signals.jsonl for retry."""
        state = self._load_retry_state()

        if signal_id not in state:
            return {"retried": False, "signal_id": signal_id, "reason": "not_found"}

        entry = state[signal_id]
        signal_data = entry.get("signal", {})

        # Update retry metadata
        entry["retry_count"] += 1
        entry["last_attempt_utc"] = self._now_utc()

        # Calculate new backoff
        backoff_sec = self.base_backoff_sec * (2 ** entry["retry_count"])
        backoff_until = datetime.now(timezone.utc) + timedelta(seconds=backoff_sec)
        entry["backoff_until_utc"] = backoff_until.isoformat()

        # Re-append signal to signals file
        self.signals_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.signals_file, 'a') as f:
            f.write(json.dumps(signal_data) + "\n")

        self._save_retry_state(state)

        return {
            "retried": True,
            "signal_id": signal_id,
            "attempt": entry["retry_count"]
        }

    def is_poison_pill(self, signal_id):
        """Check if a signal is a poison pill (permanently failing)."""
        state = self._load_retry_state()
        entry = state.get(signal_id, {})

        retry_count = entry.get("retry_count", 0)
        max_retries = entry.get("max_retries", self.max_retries)
        failure_reason = entry.get("failure_reason", "") or ""

        # Check if in dead letter multiple times
        dead_letter_count = 0
        if self.dead_letter_file.exists():
            with open(self.dead_letter_file, 'r') as f:
                for line in f:
                    try:
                        dl_entry = json.loads(line)
                        if dl_entry.get("signal_id") == signal_id:
                            dead_letter_count += 1
                    except json.JSONDecodeError:
                        pass

        # Determine failure type based on reason patterns
        permanent_patterns = ["syntax error", "file not found", "invalid", "missing"]
        transient_patterns = ["timeout", "connection", "network", "temporary"]

        failure_type = "unknown"
        failure_reason_lower = failure_reason.lower()

        for pattern in permanent_patterns:
            if pattern in failure_reason_lower:
                failure_type = "permanent"
                break

        if failure_type == "unknown":
            for pattern in transient_patterns:
                if pattern in failure_reason_lower:
                    failure_type = "transient"
                    break

        # Determine if poison pill
        is_poison = retry_count >= max_retries or dead_letter_count > 1

        return {
            "is_poison": is_poison,
            "reason": failure_reason,
            "retry_count": retry_count,
            "dead_letter_count": dead_letter_count,
            "failure_type": failure_type
        }

    def apply_ttl(self, ttl_minutes=120):
        """Expire signals older than TTL without completions."""
        state = self._load_retry_state()
        now = datetime.now(timezone.utc)
        ttl_cutoff = now - timedelta(minutes=ttl_minutes)

        expired_count = 0
        expired_ids = []

        # Get cursor position
        cursor_pos = 0
        if self.cursor_file.exists():
            try:
                with open(self.cursor_file, 'r') as f:
                    cursor_pos = int(f.read().strip())
            except (ValueError, FileNotFoundError):
                pass

        # Get completion signal IDs
        completed_ids = set()
        if self.completions_dir.exists():
            for cf in self.completions_dir.glob("*_completion.md"):
                # Extract signal_id from filename or content
                completed_ids.add(cf.stem.replace("_completion", ""))

        # Check signals from cursor onward
        if self.signals_file.exists():
            with open(self.signals_file, 'r') as f:
                lines = f.readlines()

            for i, line in enumerate(lines[cursor_pos:], start=cursor_pos):
                try:
                    signal = json.loads(line)
                    signal_id = signal.get("signal_id")

                    if not signal_id:
                        continue

                    # Skip if already completed
                    if signal_id in completed_ids:
                        continue

                    # Check if in retry state
                    if signal_id not in state:
                        # Signal without retry state - check timestamp
                        timestamp_str = signal.get("timestamp_utc")
                        timestamp = self._parse_utc(timestamp_str)

                        if timestamp and timestamp < ttl_cutoff:
                            # Expired - move to dead letter
                            self._move_to_dead_letter(signal_id, "ttl_expired")
                            expired_count += 1
                            expired_ids.append(signal_id)
                except json.JSONDecodeError:
                    continue

        return {"expired": expired_count, "signal_ids": expired_ids}

    def run_retry_pass(self):
        """Run single pass of retry logic."""
        results = {"retried": 0, "expired": 0, "dead_lettered": 0}

        # Step 1: Expire old signals
        expired = self.apply_ttl()
        results["expired"] = expired["expired"]

        # Step 2: Retry eligible signals
        retryable = self.get_retryable_signals()
        for sig in retryable:
            result = self.retry_signal(sig["signal_id"])
            if result.get("retried"):
                results["retried"] += 1

        return results

    def get_retry_stats(self):
        """Get summary statistics for dashboard."""
        state = self._load_retry_state()

        total_tracked = len(state)
        retrying = 0
        healthy = 0
        total_retry_count = 0
        most_retried_signal = None
        most_retries = 0

        for signal_id, entry in state.items():
            retry_count = entry.get("retry_count", 0)
            max_retries = entry.get("max_retries", self.max_retries)
            total_retry_count += retry_count

            if retry_count > most_retries:
                most_retries = retry_count
                most_retried_signal = signal_id

            if retry_count == 0:
                healthy += 1
            elif retry_count < max_retries:
                retrying += 1

        # Count dead letters
        dead_lettered = 0
        if self.dead_letter_file.exists():
            with open(self.dead_letter_file, 'r') as f:
                dead_lettered = len(f.readlines())

        avg_retry_count = total_retry_count / total_tracked if total_tracked > 0 else 0

        return {
            "total_tracked": total_tracked,
            "retrying": retrying,
            "dead_lettered": dead_lettered,
            "healthy": healthy,
            "average_retry_count": round(avg_retry_count, 2),
            "most_retried_signal": most_retried_signal,
            "most_retries": most_retries
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Signal retry manager")
    parser.add_argument("--agent-dir", required=True)
    parser.add_argument("--agent-name", help="Agent name for cursor file (default: dirname)")
    parser.add_argument("--mark-failed", nargs=2, metavar=("SIGNAL_ID", "REASON"))
    parser.add_argument("--retry-pass", action="store_true", help="Run one retry pass")
    parser.add_argument("--check-poison", metavar="SIGNAL_ID")
    parser.add_argument("--apply-ttl", type=int, metavar="MINUTES", default=120)
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    manager = RetryManager(args.agent_dir, agent_name=getattr(args, 'agent_name', None))

    if args.mark_failed:
        result = manager.mark_failed(args.mark_failed[0], args.mark_failed[1])
        print(json.dumps(result, indent=2))
    elif args.retry_pass:
        result = manager.run_retry_pass()
        print(json.dumps(result, indent=2))
    elif args.check_poison:
        result = manager.is_poison_pill(args.check_poison)
        print(json.dumps(result, indent=2))
    elif args.apply_ttl:
        result = manager.apply_ttl(args.apply_ttl)
        print(json.dumps(result, indent=2))
    elif args.stats:
        result = manager.get_retry_stats()
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()
