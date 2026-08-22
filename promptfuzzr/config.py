"""Run configuration: target settings, retry policy, session/authority
policy, and paths. Loaded from a YAML config file and/or CLI flags.

The SQLite database location is deliberately NOT part of this config —
see promptfuzzr/storage/paths.py. It's an application concern (always
~/.promptfuzzr/db/), not a per-run setting.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class RetryPolicy:
    """See roadmap.md section 5 — non-determinism note: retry failed
    payloads 5-10x before marking fail, log retry_count per case.
    """

    max_retries: int = 8
    backoff_seconds: float = 1.5


@dataclass
class AuthorityPolicy:
    """Declares which tools a given session role is allowed to invoke,
    with what argument constraints. The action-outcome judge compares
    the observed ToolCallRecord trace against this — it does not infer
    authorization itself.

    allowed_tools: tool names the role may call at all. Anything outside
    this list is an automatic violation regardless of arguments.

    allowed_arg_values (Phase 4): per-tool argument allow-lists, shaped
    {tool_name: {arg_name: [allowed values]}}. A call to an allowed tool
    that passes a constrained argument with a value NOT on its list is
    also a violation — e.g. delete_ticket restricted to ticket_ids owned
    by the caller. Values are compared as strings so YAML ints/strings
    and model-emitted JSON values compare uniformly.
    """

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

    # Which ModelClient to construct in cli.py::fuzz. "anthropic" reads
    # ANTHROPIC_API_KEY; "openai_compat" reads OPENAI_COMPAT_API_KEY and
    # OPENAI_COMPAT_BASE_URL (for local routers like omniroute, LiteLLM
    # proxy, etc.) — see targets/agent_harness.py for both clients.
    model_provider: str = "anthropic"
    model_name: str = "claude-sonnet-4-6"

    # Positive control: when "vulnerable", fuzz runs against the
    # deterministic no-defense VulnerableAgentModelClient instead of a
    # real model. Use it to validate the success path (judge, findings,
    # minimizer) — never to estimate real-world attack rates.
    target_profile: str = "real"

    # External agent under test exposing an OpenAI-compatible
    # /v1/chat/completions endpoint (e.g. DVAA's LegacyBot at
    # http://localhost:7003). When set, this takes precedence over
    # model_provider/target_profile: the corpus is sent straight to the
    # remote agent, which brings its own system prompt and tools.
    agent_endpoint: str | None = None

    # Phase 3: which delivery surface and propagation mode this run uses.
    # delivery: direct | webpage | email | file | repo_comment | rag_doc | tool_schema
    # propagation: single_shot | multi_step | cross_session
    delivery: str = "direct"
    propagation: str = "single_shot"

    # Phase 4: multi-step propagation sends up to this many follow-up
    # turns after the initial trigger (context-hijack pushes like
    # "proceed with the instructions you found").
    max_follow_up_turns: int = 2

    @classmethod
    def from_yaml(cls, path: Path) -> "RunConfig":
        """Load a RunConfig from a YAML file. Only `target_id` and
        `corpus_dir` are required; everything else falls back to the
        dataclass defaults above. See config/lab.example.yaml for the
        expected shape.

        `corpus_dir` is resolved to an absolute path relative to the
        CONFIG FILE's own directory, not the process's current working
        directory. This is what makes a relative path in the YAML (e.g.
        "promptfuzzr/corpus/seeds") portable across machines and
        invocation locations — `promptfuzzr fuzz --config config/lab.yaml`
        resolves correctly whether you run it from the project root or
        somewhere else, without hardcoding an absolute, user-specific
        path into a file meant to be shared/committed.

        A `db_path` key is deliberately NOT read from the YAML, even if
        present — the database location is always
        promptfuzzr.storage.paths.get_db_path() (~/.promptfuzzr/db/),
        not a per-run setting. If an old config file still has a
        `db_path` key (e.g. from before this was centralized), it's
        ignored with a warning rather than silently doing nothing, so
        the mismatch between what's in the file and what actually
        happens isn't a surprise.
        """
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
