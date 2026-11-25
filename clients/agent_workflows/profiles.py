"""Installed role defaults, capability checks, and owned file updates."""
import hashlib
import json
import os
from pathlib import Path

from setup import atomic_private


MODEL = "gpt-6.2-sol"
MANAGER = "manager"
RECOMMENDATIONS_FILE = Path("clients/agent_workflows/recommendations.json")
ROLES = {
    "manager": ("low", "Route Loom requests and reconcile follow-ups.", ""),
    "job-entry": (
        "high", "Prepare and verify a new Loom Job that needs code or new execution contracts.",
        "Use the parent request and the connected Loom contract. Prepare the smallest producer, "
        "Profile and Unit plan that satisfies the request. Preserve exact revisions, inputs, "
        "resource choices, output storage and publication conditions. Verify the code and report "
        "the ready-to-submit plan, verified evidence, and any unresolved outcome-changing choice.",
    ),
    "history": (
        "low", "Find prior Loom decisions and incident evidence.",
        "Read only the relevant supplied records or authorized read tools. Return exact record "
        "references, cause and intervention. Distinguish a similar symptom from a confirmed match.",
    ),
    "experiment-analysis": (
        "medium", "Interpret comparable Loom evaluation evidence.",
        "Check denominators, frozen splits, seeds and success predicates before comparing. "
        "Return the comparisons that are supported, significant limitations and exact evidence.",
    ),
    "runtime-diagnosis": (
        "medium", "Diagnose Loom runtime and startup failures.",
        "Check the exact Unit and Attempt, stage, resource return and Runtime/Profile pins. "
        "Return the first verified failure and the smallest diagnostic or repair proposal.",
    ),
    "output-review": (
        "medium", "Check Loom publication, evidence and lineage.",
        "Match exact Attempts, artifact revisions, storage identities, manifests and expected inputs. "
        "Reuse accepted verification receipts. Report the missing or conflicting field.",
    ),
    "performance-analysis": (
        "medium", "Diagnose execution and coordination bottlenecks.",
        "Separate setup, queue, execution, validation and orchestration. Compare useful throughput "
        "with a fixed workload and state what was measured.",
    ),
    "experiment-design": (
        "high", "Review experimental design before expensive Loom execution.",
        "Check the split, controls, allowed stopping and checkpoint selection, and what the "
        "planned result can establish. Return only decisions material to the experiment.",
    ),
    "simulation-diagnosis": (
        "high", "Diagnose physical and control discrepancies in simulation.",
        "Trace observation, raw policy command, guard decisions, applied controls and contact "
        "in time order. Separate measured differences, hypotheses and next diagnostics.",
    ),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def profile_text(role, settings):
    _, description, instructions = ROLES[role]
    content = {
        "name": "loom-" + role,
        "description": description,
        "model": settings["model"],
        "model_reasoning_effort": settings["effort"],
        "developer_instructions": instructions + " Work only within the assigned scope. "
        "Return evidence and files to the parent. Leave Loom Job submission, queue changes, "
        "recovery writes, and final user reporting to the parent.",
    }
    return "".join(f"{key} = {json.dumps(value, ensure_ascii=False)}\n" for key, value in content.items())


def supported(models, value):
    return value["effort"] in models.get(value["model"], ())


class Profiles:
    def __init__(self, journal_root, codex_home):
        self.path = journal_root / "profiles.json"
        self.destination = codex_home / "agents"

    def read(self):
        if self.path.is_symlink():
            raise PermissionError("Refusing a symlink profile manifest")
        if not self.path.exists():
            return {"settings": {}, "files": {}}
        return json.loads(self.path.read_text())

    @staticmethod
    def recommendations(path=None):
        path = path or Path(__file__).with_name("recommendations.json")
        content = json.loads(path.read_text())
        if content["schema"] != 1 or not isinstance(content["roles"], dict):
            raise ValueError("Unsupported workflow recommendation data")
        recommendations = {}
        for role, (effort, _, _) in ROLES.items():
            value = content["roles"].get(role, {"model": MODEL, "effort": effort})
            if not isinstance(value, dict) or set(value) != {"model", "effort"} or not all(
                isinstance(v, str) and v for v in value.values()
            ):
                raise ValueError("Invalid workflow recommendation")
            recommendations[role] = value
        return recommendations

    def report(self, models=None, recommendations=None):
        state = self.read()
        roles = {}
        for role, recommended in (recommendations or self.recommendations()).items():
            current = state["settings"].get(role)
            status = "unset" if current is None else "unverified"
            if models is not None and current is not None:
                status = "available" if supported(models, current) else "unavailable"
            info = {"current": current, "recommended": recommended, "status": status}
            if models is not None:
                info["recommended_available"] = supported(models, recommended)
                info["different_recommendation"] = info["recommended_available"] and current not in (None, recommended)
                if status == "unavailable" or not info["recommended_available"]:
                    info["alternatives"] = [
                        {"model": name, "effort": recommended["effort"]}
                        for name, efforts in models.items()
                        if name != recommended["model"] and recommended["effort"] in efforts
                    ][:8]
            roles[role] = info
        return roles

    def install(self, models, role=None, model=None, effort=None):
        state = self.read()
        if role is not None:
            value = {"model": model, "effort": effort}
            if not supported(models, value):
                raise ValueError("The selected Codex does not advertise that model and effort")
            state["settings"][role] = value
            selected = [role]
        else:
            selected = []
            for key, preferred in self.recommendations().items():
                value = state["settings"].get(key, preferred)
                if supported(models, value):
                    state["settings"][key] = value
                    selected.append(key)
        edits = {}
        folder = self.destination
        if selected:
            if folder.is_symlink():
                raise PermissionError("Refusing a symlink Codex agent directory")
            folder.mkdir(mode=0o700, exist_ok=True)
            if not folder.is_dir() or folder.stat().st_uid != os.getuid():
                raise PermissionError("Codex agent directory must be owned by this user")
        for key in selected:
            if key == MANAGER:
                continue
            name = "loom-" + key + ".toml"
            path = folder / name
            new = profile_text(key, state["settings"][key])
            if path.is_symlink():
                raise PermissionError("Existing agent profile is a symlink: " + name)
            previous = path.read_bytes() if path.is_file() else None
            if previous is not None and previous != new.encode() and digest(previous) != state["files"].get(name):
                raise ValueError("Existing custom agent profile was edited outside Loom Use: " + name)
            if previous != new.encode():
                edits[path] = (previous, new)
            state["files"][name] = digest(new.encode())
        written = []
        try:
            for path, (previous, new) in edits.items():
                current = path.read_bytes() if path.is_file() else None
                if current != previous or path.is_symlink():
                    raise ValueError("An agent profile changed during installation")
                atomic_private(path, new)
                written.append(path)
            atomic_private(self.path, json.dumps(state, indent=2) + "\n")
        except BaseException:
            for path in reversed(written):
                previous, new = edits[path]
                if not path.is_symlink() and path.read_bytes() == new.encode():
                    if previous is None:
                        path.unlink()
                    else:
                        atomic_private(path, previous.decode())
            raise
        return self.report(models)
