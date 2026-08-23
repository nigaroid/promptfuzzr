from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class RetryPolicy:
    max_retries: int = 8
    backoff_seconds: float = 1.5


@dataclass
class AuthorityPolicy:
    role: str
    allowed_tools: list[str] = field(default_factory=list)
    allowed_arg_values: dict[str, dict[str, list]] = field(default_factory=dict)


@dataclass
class RunConfig:
    target_id: str
    corpus_dir: Path
    axes: list[str] = field(default_factory=lambda: ["delivery", "encoding"])
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    authority_policy: AuthorityPolicy | None = None
    concurrency: int = 4

    model_provider: str = "anthropic"
    model_name: str = "claude-sonnet-4-6"

    target_profile: str = "real"

    agent_endpoint: str | None = None

    delivery: str = "direct"
    propagation: str = "single_shot"

    max_follow_up_turns: int = 2

    @classmethod
    def from_yaml(cls, path: Path) -> "RunConfig":
        path = Path(path)
        config_dir = path.parent.resolve()
        raw = yaml.safe_load(path.read_text())

        if "db_path" in raw:
            warnings.warn(
                f"{path}: 'db_path' is set but is no longer a valid config field — "
                "the database location is always managed by the application "
                "(~/.promptfuzzr/db/) and can't be overridden via YAML. "
                "Remove 'db_path' from this file; it is being ignored.",
                stacklevel=2,
            )

        def _resolve(raw_path: str) -> Path:
            p = Path(raw_path)
            return p if p.is_absolute() else (config_dir / p).resolve()

        retry_raw = raw.get("retry_policy", {})
        retry_policy = RetryPolicy(
            max_retries=retry_raw.get("max_retries", RetryPolicy.max_retries),
            backoff_seconds=retry_raw.get("backoff_seconds", RetryPolicy.backoff_seconds),
        )

        authority_policy = None
        auth_raw = raw.get("authority_policy")
        if auth_raw:
            authority_policy = AuthorityPolicy(
                role=auth_raw["role"],
                allowed_tools=auth_raw.get("allowed_tools", []),
                allowed_arg_values=auth_raw.get("allowed_arg_values", {}),
            )

        return cls(
            target_id=raw["target_id"],
            corpus_dir=_resolve(raw["corpus_dir"]),
            axes=raw.get("axes", ["delivery", "encoding"]),
            retry_policy=retry_policy,
            authority_policy=authority_policy,
            concurrency=raw.get("concurrency", 4),
            model_provider=raw.get("model_provider", "anthropic"),
            model_name=raw.get("model_name", "claude-sonnet-4-6"),
            target_profile=raw.get("target_profile", "real"),
            agent_endpoint=raw.get("agent_endpoint"),
            delivery=raw.get("delivery", "direct"),
            propagation=raw.get("propagation", "single_shot"),
            max_follow_up_turns=raw.get("max_follow_up_turns", 2),
        )
