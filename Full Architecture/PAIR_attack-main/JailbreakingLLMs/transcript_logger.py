"""
TranscriptLogger — Generates structured JSON transcripts for PAIR attacks.

Captures per-stream, per-iteration data including attacker reasoning,
adversarial prompts, target responses, and judge scores. Designed for
downstream consumption by Z3 formal-method verification.
"""

import json
import os
from datetime import datetime, timezone


# Maps stream index (mod 3) to the strategy name from system_prompts.py
STRATEGY_NAMES = ["roleplaying", "logical_appeal", "authority_endorsement"]


class TranscriptLogger:
    def __init__(self, args, system_prompts):
        self.attack_model = args.attack_model
        self.target_model = args.target_model
        self.judge_model = args.judge_model
        self.goal = args.goal
        self.target_str = args.target_str
        self.n_streams = args.n_streams
        self.n_iterations = args.n_iterations
        self.timestamp = datetime.now(timezone.utc).isoformat()

        # Config snapshot
        from config import ATTACK_TEMP, ATTACK_TOP_P, TARGET_TEMP, TARGET_TOP_P
        self.config = {
            "attack_temperature": ATTACK_TEMP,
            "attack_top_p": ATTACK_TOP_P,
            "target_temperature": TARGET_TEMP,
            "target_top_p": TARGET_TOP_P,
            "target_max_tokens": args.target_max_n_tokens,
            "attack_max_tokens": args.attack_max_n_tokens,
            "max_n_attack_attempts": args.max_n_attack_attempts,
            "keep_last_n": args.keep_last_n,
        }

        # Assign strategy names to each stream
        num_strategies = len(system_prompts)
        self.stream_strategies = [
            STRATEGY_NAMES[i % num_strategies] if i % num_strategies < len(STRATEGY_NAMES) else f"strategy_{i % num_strategies}"
            for i in range(self.n_streams)
        ]

        # Per-stream iteration data: streams[stream_id] = list of iteration dicts
        self.streams = {i: [] for i in range(self.n_streams)}

        # Tracking
        self.is_jailbroken = False
        self.queries_to_jailbreak = None
        self.max_score = 0

        # Output directory
        self.transcript_dir = getattr(args, 'transcript_dir', 'transcripts')

    def log(self, iteration, attack_list, response_list, judge_scores):
        """Log one iteration of data across all streams."""
        for i in range(len(attack_list)):
            score = judge_scores[i]
            self.max_score = max(self.max_score, score)

            iteration_data = {
                "iteration": iteration,
                "improvement": attack_list[i].get("improvement", ""),
                "adversarial_prompt": attack_list[i].get("prompt", ""),
                "target_response": response_list[i],
                "judge_score": score,
            }
            self.streams[i].append(iteration_data)

            # Track first jailbreak
            if score == 10 and not self.is_jailbroken:
                self.is_jailbroken = True
                self.queries_to_jailbreak = self.n_streams * (iteration - 1) + i + 1

    def finish(self):
        """Build and write the final JSON transcript."""
        # Build streams array
        streams_output = []
        for stream_id in range(self.n_streams):
            iterations = self.streams[stream_id]
            scores = [it["judge_score"] for it in iterations]
            stream_max = max(scores) if scores else 0

            streams_output.append({
                "stream_id": stream_id,
                "attacker_strategy": self.stream_strategies[stream_id],
                "jailbroken": any(s == 10 for s in scores),
                "max_score": stream_max,
                "iterations": iterations,
                "score_trajectory": scores,
            })

        transcript = {
            "attack_type": "pair",
            "goal": self.goal,
            "target_str": self.target_str,
            "target_model": self.target_model,
            "attacker_model": self.attack_model,
            "judge_model": self.judge_model,
            "timestamp": self.timestamp,
            "success": self.is_jailbroken,
            "max_score": self.max_score,
            "queries_to_jailbreak": self.queries_to_jailbreak,
            "n_streams": self.n_streams,
            "n_iterations": self.n_iterations,
            "config": self.config,
            "streams": streams_output,
        }

        # Write to file
        os.makedirs(self.transcript_dir, exist_ok=True)

        # Generate descriptive filename
        attacker_short = self.attack_model.replace("/", "-").replace(":", "-")
        target_short = self.target_model.replace("/", "-").replace(":", "-")
        goal_short = self.goal[:40].replace(" ", "_").replace("/", "-").lower()
        timestamp_short = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"pair_{attacker_short}_vs_{target_short}_{goal_short}_{timestamp_short}.json"
        filepath = os.path.join(self.transcript_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(transcript, f, indent=2, ensure_ascii=False)

        print(f"\n[TRANSCRIPT] Saved to: {filepath}")
        return filepath
